"""Short SQLite transactions shared by the coordinator and pytest workers."""
from contextlib import closing, contextmanager
import json
from pathlib import Path
import sqlite3
import time
import uuid

from .cleanup import DECLARED_SOURCE_SCHEMA, SCHEMA as OUTBOX_SCHEMA
from .values import freeze_expected
from .status import advance_observation, finish_request, record_observation, record_poll_error, timeout_result

TERMINAL = ("PASSED", "FAILED", "ERROR", "CANCELLED")
REQUEST_SCHEMA = """
CREATE TABLE request (id INTEGER PRIMARY KEY, attempt INTEGER NOT NULL REFERENCES attempt(id),
 step TEXT NOT NULL, source TEXT NOT NULL, correlation TEXT, rules TEXT NOT NULL, inputs TEXT NOT NULL,
 deadline REAL NOT NULL, next_poll REAL NOT NULL DEFAULT 0, version INTEGER, expires REAL,
 state TEXT NOT NULL DEFAULT 'PREPARED', claim TEXT,
 semantics INTEGER NOT NULL DEFAULT 1, evidence_view TEXT NOT NULL DEFAULT 'single_partition',
 last_observation TEXT, last_poll_error TEXT, poll_terminal INTEGER NOT NULL DEFAULT 0,
 UNIQUE(source,correlation), UNIQUE(attempt,step,source));
"""
_SCHEMA = """
CREATE TABLE run (id TEXT PRIMARY KEY, workspace TEXT NOT NULL, settings TEXT NOT NULL,
 epoch INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL, started REAL NOT NULL,
 finished REAL, exit_code INTEGER, url_hash TEXT, token_hash TEXT, salt TEXT NOT NULL,
 pytest_exit INTEGER, published INTEGER NOT NULL DEFAULT 0, metadata TEXT NOT NULL DEFAULT '{}');
CREATE TABLE unit (idx INTEGER PRIMARY KEY, report_path TEXT NOT NULL, selection TEXT NOT NULL, env_files TEXT NOT NULL);
CREATE TABLE preflight (id TEXT PRIMARY KEY, unit INTEGER NOT NULL REFERENCES unit(idx),
 sources TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending', reason TEXT);
CREATE TABLE attempt (id INTEGER PRIMARY KEY, unit INTEGER NOT NULL REFERENCES unit(idx),
 nodeid TEXT NOT NULL, number INTEGER NOT NULL, worker TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'RUNNING', UNIQUE(unit,nodeid,number));
CREATE TABLE phase (attempt INTEGER NOT NULL REFERENCES attempt(id), name TEXT NOT NULL,
 outcome TEXT NOT NULL, PRIMARY KEY(attempt,name));
""" + REQUEST_SCHEMA + """
CREATE TABLE result (request INTEGER PRIMARY KEY REFERENCES request(id), payload TEXT NOT NULL);
CREATE INDEX request_queue ON request(state,next_poll,deadline);
PRAGMA user_version=2;
"""


class RunStore:
    def __init__(self, path, epoch=None):
        self.path = Path(path)
        self.epoch = epoch

    def connect(self):
        db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=1)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def create(self, run_id, workspace, settings, metadata):
        self.path.touch(mode=0o600, exist_ok=False)
        with closing(self.connect()) as db, db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(_SCHEMA + OUTBOX_SCHEMA)
            db.execute("INSERT INTO run(id,workspace,settings,state,started,salt,metadata) VALUES(?,?,?,?,?,?,?)",
                       (run_id, str(workspace), json.dumps(settings), "RUNNING", time.time(),
                        uuid.uuid4().hex, json.dumps(metadata)))

    @contextmanager
    def snapshot(self):
        with closing(self.connect()) as db:
            db.execute("BEGIN")
            yield db

    def read(self, sql, args=()):
        with closing(self.connect()) as db:
            return [dict(row) for row in db.execute(sql, args)]

    @contextmanager
    def write(self):
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if self.epoch is not None and db.execute("SELECT epoch FROM run").fetchone()[0] != self.epoch:
                raise RuntimeError("stale log assertion run owner")
            yield db

    def own(self):
        with closing(self.connect()) as db:
            db.execute("PRAGMA foreign_keys=OFF")
            with db:
                db.execute("BEGIN IMMEDIATE")
                version = db.execute("PRAGMA user_version").fetchone()[0]
                if version == 1:
                    migrate_v1(db)
                elif version != 2:
                    raise ValueError("unsupported log assertion state format")
                db.execute("UPDATE run SET epoch=epoch+1")
                epoch, = db.execute("SELECT epoch FROM run").fetchone()
            db.execute("PRAGMA foreign_keys=ON")
        self.epoch = epoch

    def ensure_projection_tables(self):
        with closing(self.connect()) as db:
            db.executescript(OUTBOX_SCHEMA)

    def run(self):
        return self.read("SELECT * FROM run")[0]

    def update(self, sql, args=()):
        with self.write() as db:
            return db.execute(sql, args).rowcount

    def start_attempt(self, unit, nodeid, worker):
        with self.write() as db:
            number = db.execute(
                "SELECT COALESCE(MAX(number),0)+1 FROM attempt WHERE unit=? AND nodeid=?", (unit, nodeid),
            ).fetchone()[0]
            return db.execute("INSERT INTO attempt(unit,nodeid,number,worker) VALUES(?,?,?,?)",
                              (unit, nodeid, number, worker)).lastrowid

    def phase(self, attempt, name, outcome):
        with self.write() as db:
            db.execute("INSERT OR REPLACE INTO phase VALUES(?,?,?)", (attempt, name, outcome))
            if name == "teardown":
                db.execute("UPDATE attempt SET state='FINISHED' WHERE id=?", (attempt,))

    def register(self, attempt, step, source, rules, inputs, deadline, limit):
        from .discovery import group_log_rules

        groups = group_log_rules(source, rules)
        frozen = freeze_expected(inputs)
        if len(rules) != len(frozen):
            raise ValueError("log assertion rule and input counts differ")
        scoped = "source_id" in rules[0]
        with self.write() as db:
            active = db.execute("SELECT COUNT(*) FROM request WHERE state NOT IN (?,?,?,?)", TERMINAL).fetchone()[0]
            if active + len(groups) > limit:
                raise RuntimeError("log assertion pending request capacity exceeded")
            metadata, = db.execute("SELECT metadata FROM run").fetchone()
            views = json.loads(metadata).get("log_evidence_views", {})
            handles = [None] * len(rules)
            for actual, indices in groups.items():
                request = db.execute(
                    """INSERT INTO request(attempt,step,source,rules,inputs,deadline,semantics,evidence_view)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (attempt, step, actual, json.dumps([rules[i] for i in indices]),
                     json.dumps([frozen[i] for i in indices]), deadline, 2 if scoped else 1,
                     views.get(actual, "single_partition")),
                ).lastrowid
                for index in indices:
                    handles[index] = request
        return tuple(handles) if scoped else handles[0]

    def bind(self, request, correlation):
        handles = _handles(request)
        with self.write() as db:
            candidates = _prepared_rows(db, handles, bound=False)
            conflicts = []
            for candidate in candidates:
                original = db.execute("SELECT id FROM request WHERE source=? AND correlation=?",
                                      (candidate["source"], correlation)).fetchone()
                if original is not None:
                    conflicts.append((original["id"],))
            if conflicts:
                db.executemany("INSERT OR IGNORE INTO association_conflict VALUES(?)", conflicts)
            else:
                db.executemany("UPDATE request SET correlation=? WHERE id=?",
                               [(correlation, candidate["id"]) for candidate in candidates])
        if conflicts:
            raise RuntimeError("log assertion correlation already belongs to a different request")

    def freeze(self, request, inputs):
        frozen = freeze_expected(inputs)
        with self.write() as db:
            rows = _prepared_rows(db, _handles(request), bound=True)
            if isinstance(request, tuple):
                if len(request) != len(frozen):
                    raise ValueError("log assertion rule and input counts differ")
                by_request = {rid: [] for rid in request}
                for rid, values in zip(request, frozen):
                    by_request[rid].append(values)
            else:
                by_request = {request: frozen}
            for row in rows:
                db.execute("UPDATE request SET inputs=?,state='WAITING' WHERE id=?",
                           (json.dumps(by_request[row["id"]]), row["id"]))
                if row["semantics"] == 2 or row["last_observation"] or row["poll_terminal"]:
                    advance_observation(db, row, time.time())

    def fail(self, request, code):
        with self.write() as db:
            rows = _prepared_rows(db, _handles(request))
            for row in rows:
                finish_request(db, row["id"], "ERROR", code)

    def complete(self, request, state, result, *, claim=None):
        with self.write() as db:
            if claim is None:
                cursor = db.execute("UPDATE request SET state=?,claim=NULL WHERE id=? AND state NOT IN (?,?,?,?)",
                                    (state, request, *TERMINAL))
            else:
                cursor = db.execute("UPDATE request SET state=?,claim=NULL WHERE id=? AND state='RUNNING' AND claim=?",
                                    (state, request, claim))
            if cursor.rowcount:
                db.execute("INSERT INTO result VALUES(?,?)", (request, json.dumps(result)))
            return bool(cursor.rowcount)

    def claim(self, request):
        token = uuid.uuid4().hex
        if self.update("UPDATE request SET state='RUNNING',claim=? WHERE id=? AND state='READY'", (token, request)):
            return token
        return None

    def recover(self):
        self.update("UPDATE attempt SET state='INTERRUPTED' WHERE state='RUNNING'")
        self.close_prepared()
        self.update("UPDATE request SET state='WAITING', claim=NULL,next_poll=0 WHERE state IN ('READY','RUNNING')")

    def close_prepared(self, unit=None):
        sql = ("SELECT request.* FROM request JOIN attempt ON attempt.id=request.attempt "
               "WHERE request.state='PREPARED'")
        args = ()
        if unit is not None:
            sql += " AND attempt.unit=?"
            args = (unit,)
        with self.write() as db:
            steps = {}
            for row in db.execute(sql, args):
                steps.setdefault((row["attempt"], row["step"]), []).append(row)
            for rows in steps.values():
                bound = all(row["correlation"] for row in rows)
                dynamic = any("from_response" in provider for row in rows
                              for rule in json.loads(row["rules"])
                              for provider in rule.get("expected", {}).values())
                for row in rows:
                    if bound and not dynamic:
                        db.execute("UPDATE request SET state='WAITING',next_poll=0 WHERE id=?", (row["id"],))
                        if row["semantics"] == 2 or row["last_observation"] or row["poll_terminal"]:
                            advance_observation(db, row, time.time())
                    else:
                        finish_request(db, row["id"], "ERROR", "LOG_INPUT_ERROR" if bound else "LOG_BINDING_ERROR")

    def observe(self, entries, now, delay):
        with self.write() as db:
            for request, observation, expires in entries:
                record_observation(db, request, observation, expires, now, delay)

    def poll_error(self, request, code, now, delay, retryable):
        with self.write() as db:
            record_poll_error(db, request, code, now, delay, retryable)

    def expire_waiting(self, now, *, include_waiting=True):
        with self.write() as db:
            for row in db.execute(
                "SELECT id,deadline,expires,semantics,last_observation,last_poll_error FROM request "
                "WHERE (state='READY' OR (state='WAITING' AND ?)) AND (deadline<=? OR expires<=?)",
                (include_waiting, now, now),
            ).fetchall():
                state, code = timeout_result(row, now)
                finish_request(db, row["id"], state, code)


def _handles(request):
    return tuple(dict.fromkeys(request)) if isinstance(request, tuple) else (request,)


def _prepared_rows(db, handles, bound=None):
    rows = []
    for handle in handles:
        row = db.execute("SELECT * FROM request WHERE id=? AND state='PREPARED'", (handle,)).fetchone()
        if row is None or (bound is not None and (row["correlation"] is not None) != bound):
            raise RuntimeError("log assertion request is no longer open")
        rows.append(row)
    return rows


def migrate_v1(db):
    columns = "id,attempt,step,source,correlation,rules,inputs,deadline,next_poll,version,expires,state,claim"
    db.execute(REQUEST_SCHEMA.replace("CREATE TABLE request ", "CREATE TABLE request_v2 ", 1))
    db.execute(f"INSERT INTO request_v2 ({columns}) SELECT {columns} FROM request")
    old_count, = db.execute("SELECT COUNT(*) FROM request").fetchone()
    new_count, = db.execute("SELECT COUNT(*) FROM request_v2").fetchone()
    if old_count != new_count:
        raise ValueError("log assertion request migration lost rows")
    db.execute("DROP TABLE request")
    db.execute("ALTER TABLE request_v2 RENAME TO request")
    db.execute("CREATE INDEX request_queue ON request(state,next_poll,deadline)")
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("log assertion state has invalid references")
    db.execute(DECLARED_SOURCE_SCHEMA)
    db.execute("PRAGMA user_version=2")
