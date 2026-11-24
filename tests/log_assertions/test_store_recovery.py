"""Verify durable claims and run-owner fencing."""
from dataclasses import asdict
import json
import time

import pytest

from aitest_kit.log_assertions.config import RunSettings
from aitest_kit.log_assertions.run import owner_lock
from aitest_kit.log_assertions.store import RunStore


def test_recovery_preserves_frozen_input_and_rejects_stale_owner(tmp_path):
    path = tmp_path / "log-assertions.sqlite3"
    first = RunStore(path)
    first.create("example", tmp_path, asdict(RunSettings()), {})
    with owner_lock(tmp_path):
        first.own()
        with pytest.raises(ValueError, match="another process"), owner_lock(tmp_path):
            pytest.fail("two coordinators hold the same run lock")
        first.update("INSERT INTO unit VALUES(?,?,?,?)", (0, str(tmp_path), "[]", "[]"))
        attempt = first.start_attempt(0, "test_a.py::test_query[param]", "gw0")
        request = first.register(attempt, "reply", "source", [{"executor_version": 1}], [{}], 123456, 10)
        first.bind(request, "example")
        first.freeze(request, [{"score": 1}])
        first.update("UPDATE request SET state='READY' WHERE id=?", (request,))
        claim = first.claim(request)

    with owner_lock(tmp_path):
        second = RunStore(path)
        second.own()
        second.recover()
        row, = second.read("SELECT * FROM request")
        assert (row["state"], row["correlation"], row["deadline"], row["inputs"]) == (
            "WAITING", "example", 123456, '[{"score": 1}]',
        )
        with pytest.raises(RuntimeError, match="stale"):
            first.complete(request, "PASSED", {"state": "PASSED"}, claim=claim)
        second.update("UPDATE request SET state='READY' WHERE id=?", (request,))
        live_claim = second.claim(request)
        assert live_claim != claim
        assert not second.complete(request, "PASSED", {"state": "PASSED"}, claim=claim)
        assert second.complete(request, "PASSED", {"state": "PASSED"}, claim=live_claim)
        assert len(second.read("SELECT * FROM result")) == 1


def test_grouped_store_capacity_binding_conflict_and_input_pairing(tmp_path):
    store = RunStore(tmp_path / "run.sqlite3")
    store.create("example", tmp_path, asdict(RunSettings()), {})
    store.own()
    store.update("INSERT INTO unit VALUES(0,?,'[]','[]')", (str(tmp_path),))
    attempt = store.start_attempt(0, "case", "main")
    rules = [
        {"source_id": "main", "group_index": 4},
        {"source_id": "perf", "group_index": 7},
        {"source_id": "main", "group_index": 9},
    ]
    deadline = time.time() + 30
    with pytest.raises(RuntimeError, match="capacity"):
        store.register(attempt, "reply", "anchor", rules, [{}, {}, {}], deadline, 1)
    assert store.read("SELECT id FROM request") == []
    handle = store.register(attempt, "reply", "anchor", rules, [{}, {}, {}], deadline, 2)
    store.bind(handle, "shared")
    store.freeze(handle, [{"value": 4}, {"value": 7}, {"value": 9}])
    assert store.read("SELECT source,inputs,deadline FROM request ORDER BY id") == [
        {"source": "main", "inputs": '[{"value": 4}, {"value": 9}]', "deadline": deadline},
        {"source": "perf", "inputs": '[{"value": 7}]', "deadline": deadline},
    ]
    next_handle = store.register(attempt, "second", "anchor", rules, [{}, {}, {}], deadline, 4)
    with pytest.raises(RuntimeError, match="already belongs"):
        store.bind(next_handle, "shared")
    assert store.read("SELECT DISTINCT correlation FROM request WHERE step='second'") == [{"correlation": None}]
    assert store.read("SELECT request FROM association_conflict ORDER BY request") == [
        {"request": handle[0]}, {"request": handle[1]},
    ]


@pytest.mark.parametrize("status,error,expected", [
    ("NOT_FOUND", None, ("FAILED", "LOG_READINESS_TIMEOUT")),
    ("COLLECTING", None, ("FAILED", "LOG_READINESS_TIMEOUT")),
    ("COMPLETE", None, ("ERROR", "LOG_EVIDENCE_TIMEOUT")),
    (None, None, ("ERROR", "LOG_EVIDENCE_TIMEOUT")),
    ("COLLECTING", "PLATFORM_NETWORK_ERROR", ("ERROR", "PLATFORM_NETWORK_ERROR")),
])
def test_grouped_timeout_uses_persisted_observations(tmp_path, status, error, expected):
    from aitest_kit.log_assertions.status import observation_for

    store = RunStore(tmp_path / "run.sqlite3")
    store.create("example", tmp_path, asdict(RunSettings()), {})
    store.own()
    store.update("INSERT INTO unit VALUES(0,?,'[]','[]')", (str(tmp_path),))
    attempt = store.start_attempt(0, "case", "main")
    now = time.time()
    handle = store.register(attempt, "reply", "anchor", [{"source_id": "perf"}], [{}], now + 10, 1)
    store.bind(handle, "shared")
    store.freeze(handle, [{}])
    if status:
        payload = {"result": "NOT_FOUND", "request": None} if status == "NOT_FOUND" else {
            "result": "FOUND", "request": {"capture_state": status, "availability": "AVAILABLE", "version": 1},
        }
        store.observe([(handle[0], observation_for(payload, now + 1), None)], now + 1, .05)
    if error:
        store.poll_error(handle[0], error, now + 2, .05, True)
    reopened = RunStore(store.path)
    reopened.own()
    reopened.recover()
    reopened.expire_waiting(now + 10)
    result, = reopened.read("SELECT state,payload FROM request JOIN result ON request.id=result.request")
    assert (result["state"], json.loads(result["payload"])["code"]) == expected


def test_migrate_v1_preserves_references_and_fences_former_owner(tmp_path, monkeypatch):
    from contextlib import closing
    from aitest_kit.log_assertions import store as state_store

    store = RunStore(tmp_path / "run.sqlite3")
    v1_request = """CREATE TABLE request (id INTEGER PRIMARY KEY, attempt INTEGER NOT NULL REFERENCES attempt(id),
        step TEXT NOT NULL, source TEXT NOT NULL, correlation TEXT, rules TEXT NOT NULL, inputs TEXT NOT NULL,
        deadline REAL NOT NULL, next_poll REAL NOT NULL DEFAULT 0, version INTEGER, expires REAL,
        state TEXT NOT NULL DEFAULT 'PREPARED', claim TEXT, UNIQUE(source,correlation), UNIQUE(attempt,step));"""
    with monkeypatch.context() as patch:
        patch.setattr(state_store, "_SCHEMA", state_store._SCHEMA.replace(state_store.REQUEST_SCHEMA, v1_request)
                      .replace("user_version=2", "user_version=1"))
        patch.setattr(state_store, "OUTBOX_SCHEMA", state_store.OUTBOX_SCHEMA.replace(state_store.DECLARED_SOURCE_SCHEMA, ""))
        store.create("example", tmp_path, asdict(RunSettings()), {})
    store.update("INSERT INTO unit VALUES(0,?,'[]','[]')", (str(tmp_path),))
    attempt = store.start_attempt(0, "case", "main")
    store.update("INSERT INTO request(id,attempt,step,source,correlation,rules,inputs,deadline,state)"
                 " VALUES(101,?,'reply','main','old','[]','[]',123456,'PASSED')", (attempt,))
    store.update("INSERT INTO declared_step VALUES(0,'case','reply')")
    store.update("INSERT INTO result VALUES(101,'{}')")
    store.update("INSERT INTO cleanup(request,key,deadline,next_submit,state,job_id) VALUES(101,'key',9,8,'accepted','job')")
    store.update("INSERT INTO association_conflict VALUES(101)")
    old = RunStore(store.path, epoch=0)

    def interrupted(db):
        db.execute("ALTER TABLE request RENAME TO partial")
        raise RuntimeError("interrupted")

    with monkeypatch.context() as patch:
        patch.setattr(state_store, "migrate_v1", interrupted)
        with pytest.raises(RuntimeError, match="interrupted"):
            store.own()
    assert store.read("PRAGMA user_version") == [{"user_version": 1}]
    assert store.read("SELECT id FROM request") == [{"id": 101}]
    store.own()
    assert store.read("PRAGMA user_version") == [{"user_version": 2}]
    assert store.read("PRAGMA foreign_key_check") == []
    assert store.read("SELECT id,deadline,semantics,evidence_view FROM request") == [
        {"id": 101, "deadline": 123456, "semantics": 1, "evidence_view": "single_partition"},
    ]
    assert store.read("SELECT request,key,state,job_id FROM cleanup") == [
        {"request": 101, "key": "key", "state": "accepted", "job_id": "job"},
    ]
    assert store.read("SELECT request FROM association_conflict") == [{"request": 101}]
    assert store.read("SELECT request FROM result") == [{"request": 101}]
    assert store.read("SELECT step FROM declared_step") == [{"step": "reply"}]
    with pytest.raises(RuntimeError, match="stale"):
        old.update("UPDATE request SET deadline=0")
    with closing(store.connect()) as db, db:
        db.execute("PRAGMA user_version=9")
    with pytest.raises(ValueError, match="unsupported"):
        RunStore(store.path).own()


def test_grouped_freeze_rolls_back_when_one_source_write_fails(tmp_path):
    import sqlite3

    store = RunStore(tmp_path / "run.sqlite3")
    store.create("example", tmp_path, asdict(RunSettings()), {})
    store.own()
    store.update("INSERT INTO unit VALUES(0,?,'[]','[]')", (str(tmp_path),))
    attempt = store.start_attempt(0, "case", "main")
    rules = [{"source_id": source} for source in ("main", "perf")]
    handle = store.register(attempt, "reply", "anchor", rules, [{}, {}], time.time() + 30, 2)
    store.bind(handle, "shared")
    store.update("""CREATE TRIGGER reject_perf BEFORE UPDATE OF inputs ON request
                    WHEN OLD.source='perf' BEGIN SELECT RAISE(ABORT, 'second write failed'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="second write failed"):
        store.freeze(handle, [{"value": 1}, {"value": 2}])
    assert store.read("SELECT DISTINCT state,inputs FROM request") == [{"state": "PREPARED", "inputs": "[{}]"}]


def test_grouped_capacity_serializes_independent_connections(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    store = RunStore(tmp_path / "run.sqlite3")
    store.create("example", tmp_path, asdict(RunSettings()), {})
    store.own()
    store.update("INSERT INTO unit VALUES(0,?,'[]','[]')", (str(tmp_path),))
    attempts = [store.start_attempt(0, nodeid, "main") for nodeid in ("one", "two")]
    barrier = Barrier(2, timeout=5)

    def register(attempt):
        worker = RunStore(store.path, store.epoch)
        barrier.wait()
        try:
            worker.register(attempt, "reply", "anchor", [{"source_id": "perf"}], [{}], time.time() + 30, 1)
        except RuntimeError as exc:
            assert "capacity" in str(exc)
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(register, attempts)) == [False, True]
    assert store.read("SELECT COUNT(*) AS count FROM request") == [{"count": 1}]


@pytest.mark.parametrize("dynamic", [False, True])
def test_grouped_recovery_closes_unfrozen_step_as_one_unit(tmp_path, dynamic):
    from aitest_kit.log_assertions.status import observation_for

    store = RunStore(tmp_path / "run.sqlite3")
    store.create("example", tmp_path, asdict(RunSettings()), {})
    store.own()
    store.update("INSERT INTO unit VALUES(0,?,'[]','[]')", (str(tmp_path),))
    attempt = store.start_attempt(0, "case", "main")
    now = time.time()
    rules = [{"source_id": "main"}, {"source_id": "perf",
             "expected": {"score": {"from_response": "/score"}} if dynamic else {}}]
    handle = store.register(attempt, "reply", "anchor", rules, [{}, {}], now + 30, 2)
    store.bind(handle, "shared")
    meta = {"result": "FOUND", "request": {"capture_state": "COMPLETE", "availability": "AVAILABLE", "version": 1}}
    store.observe([(handle[0], observation_for(meta, now), None)], now, .05)
    owner = RunStore(store.path)
    owner.own()
    owner.recover()
    assert owner.read("SELECT source,state,correlation FROM request ORDER BY id") == [
        {"source": "main", "state": "ERROR" if dynamic else "WAITING", "correlation": "shared"},
        {"source": "perf", "state": "ERROR" if dynamic else "WAITING", "correlation": "shared"},
    ]
    assert [json.loads(row["payload"])["code"] for row in owner.read("SELECT payload FROM result")] == (
        ["LOG_INPUT_ERROR", "LOG_INPUT_ERROR"] if dynamic else []
    )


@pytest.mark.parametrize("scenario,expected", [
    ("late_resume", ("FAILED", "LOG_READINESS_TIMEOUT")),
    ("early_timeout", ("FAILED", "LOG_READINESS_TIMEOUT")),
    ("sticky_complete", ("READY", None)),
    ("legacy_403", ("ERROR", "PLATFORM_HTTP_ERROR")),
])
def test_poll_decision_survives_freeze_and_deadline(tmp_path, monkeypatch, scenario, expected):
    from aitest_kit.log_assertions.status import observation_for

    store = RunStore(tmp_path / "run.sqlite3")
    store.create("example", tmp_path, asdict(RunSettings()), {})
    store.own()
    store.update("INSERT INTO unit VALUES(0,?,'[]','[]')", (str(tmp_path),))
    attempt = store.start_attempt(0, "case", "main")
    now = time.time()
    legacy = scenario == "legacy_403"
    handle = store.register(attempt, "reply", "anchor", [{} if legacy else {"source_id": "perf"}],
                            [{}], now + 10, 1)
    request = handle if legacy else handle[0]
    store.bind(handle, "shared")
    if legacy:
        store.poll_error(request, "PLATFORM_HTTP_ERROR", now + 1, 1, False)
    else:
        capture = {"late_resume": "COLLECTING", "early_timeout": "TIMED_OUT",
                   "sticky_complete": "COMPLETE"}[scenario]
        status = {"result": "FOUND", "request": {"capture_state": capture, "availability": "AVAILABLE", "version": 1}}
        store.observe([(request, observation_for(status, now + 1), now + 15)], now + 1, .05)
        if scenario == "sticky_complete":
            assert store.read("SELECT next_poll FROM request")[0]["next_poll"] >= now + 10
            store.poll_error(request, "PLATFORM_HTTP_ERROR", now + 2, 1, False)
    with monkeypatch.context() as clock:
        clock.setattr(time, "time", lambda: now + (11 if scenario == "early_timeout" else 3))
        store.freeze(handle, [{}])
    if scenario == "late_resume":
        store.expire_waiting(now + 16)
    row, = store.read("SELECT state,payload FROM request LEFT JOIN result ON request.id=result.request")
    assert (row["state"], json.loads(row["payload"])["code"] if row["payload"] else None) == expected
