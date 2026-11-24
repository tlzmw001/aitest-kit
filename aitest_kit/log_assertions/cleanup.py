"""Persist cleanup eligibility before submitting exact request IDs."""
import asyncio
import json
import time
import uuid

from .client import LogPlatformError


IDEMPOTENCY_RETENTION_SECONDS = 3600

REPORT_NODE_SCHEMA = """
CREATE TABLE IF NOT EXISTS report_node (
 unit INTEGER NOT NULL REFERENCES unit(idx), nodeid TEXT NOT NULL, plan_key TEXT NOT NULL,
 PRIMARY KEY(unit,nodeid));
"""

DECLARED_SOURCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS declared_source (
 unit INTEGER NOT NULL REFERENCES unit(idx), nodeid TEXT NOT NULL, step TEXT NOT NULL, source TEXT NOT NULL,
 PRIMARY KEY(unit,nodeid,step,source));
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS case_closed (
 unit INTEGER NOT NULL REFERENCES unit(idx), nodeid TEXT NOT NULL, PRIMARY KEY(unit,nodeid));
CREATE TABLE IF NOT EXISTS declared_step (
 unit INTEGER NOT NULL REFERENCES unit(idx), nodeid TEXT NOT NULL, step TEXT NOT NULL,
 PRIMARY KEY(unit,nodeid,step));
""" + DECLARED_SOURCE_SCHEMA + REPORT_NODE_SCHEMA + """
CREATE TABLE IF NOT EXISTS settled_case (
 attempt INTEGER PRIMARY KEY REFERENCES attempt(id), outcome TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS association_conflict (request INTEGER PRIMARY KEY REFERENCES request(id));
CREATE TABLE IF NOT EXISTS cleanup (
 request INTEGER PRIMARY KEY REFERENCES request(id), key TEXT NOT NULL UNIQUE,
 deadline REAL NOT NULL, next_submit REAL NOT NULL, tries INTEGER NOT NULL DEFAULT 0,
 uncertain INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL DEFAULT 'queued',
 job_id TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS report_input (path TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS report_plan (payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS report_revision (revision INTEGER PRIMARY KEY);
"""


def settle(store, queue_budget):
    with store.write() as db:
        skipped = db.execute("""
            SELECT r.id FROM request r JOIN attempt a ON a.id=r.attempt
            JOIN case_closed c ON c.unit=a.unit AND c.nodeid=a.nodeid
            WHERE r.state IN ('PREPARED','WAITING','READY','RUNNING')
              AND EXISTS(SELECT 1 FROM phase p WHERE p.attempt=a.id AND p.outcome='skipped')
        """).fetchall()
        for request, in skipped:
            db.execute("UPDATE request SET state='CANCELLED',claim=NULL WHERE id=?", (request,))
            db.execute("INSERT INTO result VALUES(?,?)",
                       (request, '{"state":"CANCELLED","code":"PYTEST_SKIPPED"}'))
        attempts = db.execute("""
            SELECT a.id FROM attempt a JOIN case_closed c ON a.unit=c.unit AND a.nodeid=c.nodeid
            WHERE a.state='FINISHED'
            AND NOT EXISTS(SELECT 1 FROM attempt newer WHERE newer.unit=a.unit AND newer.nodeid=a.nodeid
                           AND newer.number>a.number)
            AND NOT EXISTS(SELECT 1 FROM settled_case s WHERE s.attempt=a.id)
            AND NOT EXISTS(SELECT 1 FROM request r WHERE r.attempt=a.id
                           AND r.state IN ('PREPARED','WAITING','READY','RUNNING'))
        """).fetchall()
        stamp = time.time()
        for attempt, in attempts:
            phases = dict(db.execute("SELECT name,outcome FROM phase WHERE attempt=?", (attempt,)))
            requests = db.execute("SELECT id,state,rules FROM request WHERE attempt=? ORDER BY id", (attempt,)).fetchall()
            if phases.get("setup") == "failed" or phases.get("teardown") == "failed":
                outcome = "error"
            elif phases.get("call") == "failed":
                outcome = "failed"
            elif "skipped" in phases.values():
                outcome = "pytest_skipped"
            elif set(phases) != {"setup", "call", "teardown"}:
                outcome = "error"
            elif db.execute("""
                SELECT 1 FROM (
                    SELECT unit,nodeid,step,NULL AS source FROM declared_step
                    UNION ALL SELECT unit,nodeid,step,source FROM declared_source
                ) d JOIN attempt a ON a.unit=d.unit AND a.nodeid=d.nodeid
                WHERE a.id=? AND NOT EXISTS (
                    SELECT 1 FROM request r WHERE r.attempt=a.id AND r.step=d.step
                    AND (d.source IS NULL OR r.source=d.source)
                )
                LIMIT 1
            """, (attempt,)).fetchone():
                outcome = "error"
            elif any(row["state"] in {"ERROR", "CANCELLED"} for row in requests):
                outcome = "error"
            elif any(row["state"] == "FAILED" for row in requests):
                outcome = "failed"
            else:
                outcome = "passed"
            db.execute("INSERT INTO settled_case VALUES(?,?)", (attempt, outcome))
            if outcome == "passed":
                for row in requests:
                    if any(rule.get("cleanup") == "on_success" for rule in json.loads(row["rules"])):
                        db.execute(
                            """INSERT INTO cleanup(request,key,deadline,next_submit)
                               SELECT ?,?,?,? WHERE NOT EXISTS(SELECT 1 FROM association_conflict WHERE request=?)""",
                            (row["id"], uuid.uuid4().hex, stamp + queue_budget, stamp, row["id"]),
                        )


def next_cleanup(store, limit=None):
    with store.write() as db:
        now = time.time()
        db.execute("""
            UPDATE cleanup SET state=CASE WHEN uncertain THEN 'unknown' ELSE 'failed' END, reason='SUBMIT_DEADLINE'
            WHERE state='queued' AND deadline<=?
        """, (now,))
        db.execute("""
            UPDATE cleanup SET state=CASE WHEN uncertain THEN 'unknown' ELSE 'failed' END, reason='ASSOCIATION_CONFLICT'
            WHERE state='queued' AND request IN (SELECT request FROM association_conflict)
        """)
        rows = db.execute("""
            SELECT cleanup.*, request.source, request.correlation FROM cleanup JOIN request ON request.id=cleanup.request
            WHERE cleanup.state='queued' AND next_submit<=? ORDER BY cleanup.deadline,cleanup.request LIMIT ?
        """, (now, limit or 1)).fetchall()
        return [dict(row) for row in rows] if limit is not None else dict(rows[0]) if rows else None


async def submit(coordinator, row):
    req = row["request"]
    db, store = coordinator.db, coordinator.store
    run = await db(store.run)
    if coordinator.binding[1] != run["token_hash"]:
        await db(store.update, "UPDATE cleanup SET state='unknown',reason='TOKEN_CHANGED' WHERE request=?", (req,))
        return
    stamp = time.time()
    submit_deadline = row["deadline"]
    if row["tries"] == 0:
        submit_deadline = stamp + min(coordinator.settings.submit_timeout_seconds, IDEMPOTENCY_RETENTION_SECONDS)
    claimed = await db(store.update, """
        UPDATE cleanup SET tries=tries+1,uncertain=1,deadline=? WHERE request=? AND deadline>? AND state='queued'
        AND NOT EXISTS(SELECT 1 FROM association_conflict WHERE request=?)
    """, (submit_deadline, req, stamp, req))
    if not claimed:
        return
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(0, submit_deadline - time.time())
    try:
        response = await coordinator.client.submit_cleanup(row["source"], [row["correlation"]], row["key"], deadline=deadline)
    except LogPlatformError as exc:
        uncertain = row["uncertain"] or exc.status is None or exc.status >= 500
        if exc.retryable or exc.code == "DEADLINE_EXCEEDED":
            settings = coordinator.settings
            delay = min(settings.retry_max_seconds, settings.retry_initial_seconds * 2 ** min(row["tries"], 30))
            await db(store.update, "UPDATE cleanup SET next_submit=?,uncertain=?,reason=? WHERE request=?",
                     (min(time.time() + max(delay, exc.retry_after or 0), submit_deadline), int(uncertain), exc.code, req))
        else:
            state = "unknown" if uncertain else "failed"
            await db(store.update, "UPDATE cleanup SET state=?,reason=? WHERE request=?", (state, exc.code, req))
    else:
        await db(store.update, "UPDATE cleanup SET state='accepted',job_id=?,reason=NULL WHERE request=?",
                 (response["job_id"], req))


def cancel_cleanup(db):
    return db.execute("""
        UPDATE cleanup SET state=CASE WHEN uncertain THEN 'unknown' ELSE 'failed' END,
        reason='CANCELLED' WHERE state='queued'
    """).rowcount


async def submit_available(coordinator):
    while not coordinator.stopping.is_set():
        rows = await coordinator.db(next_cleanup, coordinator.store, coordinator.settings.cleanup_concurrency)
        if not rows or coordinator.stopping.is_set():
            return
        tasks = [asyncio.create_task(submit(coordinator, row)) for row in rows]
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
