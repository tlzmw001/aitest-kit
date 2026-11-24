"""Persist status observations and classify evidence deadlines."""
from datetime import datetime, timezone
import json


def utc_stamp(now):
    return datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z")


def observation_for(status, now):
    entry = status["request"] or {}
    return {
        "observed_at": utc_stamp(now),
        "result": status["result"],
        **{key: entry.get(key) for key in (
            "capture_state", "availability", "version", "event_count", "expected_event_count",
        )},
    }


def finish_request(db, request, state, code):
    db.execute("UPDATE request SET state=?,claim=NULL WHERE id=?", (state, request))
    db.execute("INSERT INTO result VALUES(?,?)", (request, json.dumps({"state": state, "code": code})))


def _poll_row(db, request):
    return db.execute(
        """SELECT id,state,semantics,deadline,expires,last_observation,last_poll_error,poll_terminal
           FROM request WHERE id=? AND state IN ('PREPARED','WAITING')""", (request,),
    ).fetchone()


def _pending(observation):
    return observation["result"] == "NOT_FOUND" or (
        observation["capture_state"], observation["availability"]
    ) == ("COLLECTING", "AVAILABLE")


def _has_prepared_decision(row):
    if row["state"] != "PREPARED":
        return False
    observation = json.loads(row["last_observation"] or "null")
    return row["poll_terminal"] or (observation is not None and not _pending(observation))


def record_observation(db, request, observation, expires, now, delay):
    row = _poll_row(db, request)
    if row is None or now >= evidence_deadline(row) or _has_prepared_decision(row):
        return
    next_poll = now + delay if _pending(observation) else row["deadline"]
    serialized = json.dumps(observation)
    db.execute("""UPDATE request SET last_observation=?,last_poll_error=NULL,poll_terminal=0,version=?,
                  expires=COALESCE(?, expires),next_poll=? WHERE id=?""",
               (serialized, observation["version"], expires, next_poll, request))
    if row["state"] == "WAITING":
        advance_observation(db, {**dict(row), "last_observation": serialized, "last_poll_error": None,
                                 "poll_terminal": 0, "expires": expires if expires is not None else row["expires"]}, now)


def record_poll_error(db, request, code, now, delay, retryable):
    row = _poll_row(db, request)
    if row is None or _has_prepared_decision(row):
        return
    failure = json.dumps({"code": code, "at": utc_stamp(now)})
    db.execute("UPDATE request SET last_poll_error=?,poll_terminal=?,next_poll=? WHERE id=?",
               (failure, not retryable, now + delay if retryable else row["deadline"], request))
    if not retryable and row["state"] == "WAITING":
        finish_request(db, request, "ERROR", code)


def advance_observation(db, row, now):
    observation = json.loads(row["last_observation"] or "null")
    if row["poll_terminal"] and row["last_poll_error"]:
        finish_request(db, row["id"], "ERROR", json.loads(row["last_poll_error"])["code"])
    elif observation and not _pending(observation) and observation["capture_state"] != "COMPLETE":
        if observation["availability"] == "AVAILABLE" and observation["capture_state"] == "TIMED_OUT" and row["semantics"] == 2:
            finish_request(db, row["id"], "FAILED", "LOG_READINESS_TIMEOUT")
        else:
            finish_request(db, row["id"], "ERROR", "LOG_EVIDENCE_UNAVAILABLE")
    elif observation and observation["availability"] not in (None, "AVAILABLE"):
        finish_request(db, row["id"], "ERROR", "LOG_EVIDENCE_UNAVAILABLE")
    elif now >= evidence_deadline(row):
        state, code = timeout_result(row, now)
        finish_request(db, row["id"], state, code)
    elif not row["last_poll_error"] and observation and observation["capture_state"] == "COMPLETE":
        db.execute("UPDATE request SET state='READY' WHERE id=?", (row["id"],))


def evidence_deadline(row):
    expires = row["expires"]
    return min(row["deadline"], expires) if expires is not None else row["deadline"]


def timeout_result(row, now):
    if row["semantics"] == 2:
        if row["expires"] is not None and row["expires"] <= min(now, row["deadline"]):
            return "ERROR", "LOG_EVIDENCE_TIMEOUT"
        error = json.loads(row["last_poll_error"] or "null")
        if error:
            return "ERROR", error["code"]
        observation = json.loads(row["last_observation"] or "null")
        if observation and _pending(observation):
            return "FAILED", "LOG_READINESS_TIMEOUT"
    return "ERROR", "LOG_EVIDENCE_TIMEOUT"
