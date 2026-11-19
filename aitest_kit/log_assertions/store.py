"""Short SQLite transactions shared by the coordinator and pytest workers."""
from contextlib import closing, contextmanager
import json
from pathlib import Path
import sqlite3
import time
import uuid

from .cleanup import SCHEMA as OUTBOX_SCHEMA
from .values import freeze_expected

TERMINAL = ("PASSED", "FAILED", "ERROR", "CANCELLED")
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
CREATE TABLE request (id INTEGER PRIMARY KEY, attempt INTEGER NOT NULL REFERENCES attempt(id),
 step TEXT NOT NULL, source TEXT NOT NULL, correlation TEXT, rules TEXT NOT NULL, inputs TEXT NOT NULL,
 deadline REAL NOT NULL, next_poll REAL NOT NULL DEFAULT 0, version INTEGER, expires REAL,
 state TEXT NOT NULL DEFAULT 'PREPARED', claim TEXT, UNIQUE(source,correlation), UNIQUE(attempt,step));
CREATE TABLE result (request INTEGER PRIMARY KEY REFERENCES request(id), payload TEXT NOT NULL);
CREATE INDEX request_queue ON request(state,next_poll,deadline);
PRAGMA user_version=1;
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
        with self.write() as db:
            if db.execute("PRAGMA user_version").fetchone()[0] != 1:
                raise ValueError("unsupported log assertion state format")
            db.execute("UPDATE run SET epoch=epoch+1")
            self.epoch = db.execute("SELECT epoch FROM run").fetchone()[0]

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
        rules_json, inputs_json = json.dumps(rules), json.dumps(freeze_expected(inputs))
        with self.write() as db:
            active = db.execute("SELECT COUNT(*) FROM request WHERE state NOT IN (?,?,?,?)", TERMINAL).fetchone()[0]
            if active >= limit:
                raise RuntimeError("log assertion pending request capacity exceeded")
            return db.execute(
                "INSERT INTO request(attempt,step,source,rules,inputs,deadline) VALUES(?,?,?,?,?,?)",
                (attempt, step, source, rules_json, inputs_json, deadline),
            ).lastrowid

    def bind(self, request, correlation):
        conflict = None
        with self.write() as db:
            conflict = db.execute(
                """SELECT original.id FROM request original JOIN request candidate ON candidate.source=original.source
                   WHERE candidate.id=? AND original.correlation=? AND original.id!=candidate.id""",
                (request, correlation),
            ).fetchone()
            if conflict:
                db.execute("INSERT OR IGNORE INTO association_conflict VALUES(?)", (conflict[0],))
            elif db.execute("UPDATE request SET correlation=? WHERE id=? AND state='PREPARED' AND correlation IS NULL",
                            (correlation, request)).rowcount != 1:
                raise RuntimeError("log assertion request is no longer open")
        if conflict:
            raise RuntimeError("log assertion correlation already belongs to a different request")

    def freeze(self, request, inputs):
        if self.update("UPDATE request SET inputs=?,state='WAITING' WHERE id=? AND state='PREPARED' AND correlation IS NOT NULL",
                       (json.dumps(freeze_expected(inputs)), request)) != 1:
            raise RuntimeError("log assertion request is no longer open")

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
        self.update("UPDATE request SET state='WAITING', claim=NULL,next_poll=0 WHERE state IN ('READY','RUNNING')")
        self.close_prepared()

    def close_prepared(self, unit=None):
        sql = ("SELECT request.id, correlation, rules FROM request JOIN attempt ON attempt.id=request.attempt "
               "WHERE request.state='PREPARED'")
        args = ()
        if unit is not None:
            sql += " AND attempt.unit=?"
            args = (unit,)
        for row in self.read(sql, args):
            if row["correlation"] and not any(
                "from_response" in provider
                for rule in json.loads(row["rules"])
                for provider in rule.get("expected", {}).values()
            ):
                self.update("UPDATE request SET state='WAITING',next_poll=0 WHERE id=? AND state='PREPARED'",
                            (row["id"],))
                continue
            code = "LOG_INPUT_ERROR" if row["correlation"] else "LOG_BINDING_ERROR"
            self.complete(row["id"], "ERROR", {"state": "ERROR", "code": code})


    def expire_waiting(self, now):
        for row in self.read(
            "SELECT id FROM request WHERE state='WAITING' AND (deadline<=? OR expires<=?)", (now, now),
        ):
            self.complete(row["id"], "ERROR", {"state": "ERROR", "code": "LOG_EVIDENCE_TIMEOUT"})
