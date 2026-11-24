"""Cleanup submission and report publication through durable run facts."""
import asyncio
import json
from types import SimpleNamespace
import time

import click
import pytest

from aitest_kit.log_assertions.cleanup import next_cleanup, settle, submit
from aitest_kit.log_assertions.client import LogPlatformError
from aitest_kit.log_assertions.config import RunSettings
from aitest_kit.log_assertions.projection import publish, save_base
from aitest_kit.log_assertions.run import LogRun, resume


def make_run(root, run_id="case-run"):
    run = LogRun(root, RunSettings(retry_initial_seconds=.01))
    run.open(run_id)
    bucket = root / "reports"
    path = bucket / "runs" / run_id
    base = {"run_id": run_id, "summary": {}, "status": "COMPLETED"}
    run.store.update("INSERT INTO report_plan VALUES(?)", (json.dumps({
        "root": str(path), "bucket": str(bucket), "units": [[0, str(path)]], "base": base,
    }),))
    save_base(run.store, path, base)
    run.store.update("INSERT INTO unit VALUES(?,?,?,?)", (0, str(path), "[]", "[]"))
    return run, path


def add_attempt(run, *, node, result="PASSED", seal=True, fail_teardown=False, attempt=None, step="reply"):
    store = run.store
    attempt = attempt or store.start_attempt(0, node, "main")
    request = store.register(attempt, step, "demo", [{"cleanup": "on_success"}], [{}], time.time() + 30, 10)
    store.bind(request, f"id-{request}")
    for name in ("setup", "call", "teardown"):
        store.phase(attempt, name, "failed" if name == "teardown" and fail_teardown else "passed")
    if result:
        store.complete(request, result, {"state": result})
    if seal:
        store.update("INSERT OR IGNORE INTO case_closed VALUES(0,?)", (node,))
    return attempt


def test_cleanup_waits_for_all_requests_and_completed_pytest_protocol(tmp_path):
    run, path = make_run(tmp_path)
    try:
        passed = add_attempt(run, node="test.py::case[1]", seal=False)
        add_attempt(run, node="test.py::case[1]", result="FAILED", attempt=passed, step="another", seal=False)
        add_attempt(run, node="test.py::case[2]", fail_teardown=True)
        add_attempt(run, node="test.py::case[3]", result=None)
        settle(run.store, 30)
        publish(run.store, run.settings)
        progress = json.loads((path / "result.json").read_text())
        assert progress["summary"]["passed"] == 0
        assert progress["summary"]["pending"] == 2
        assert not progress["log_validation"]["final"]
        run.store.update("INSERT INTO case_closed VALUES(0,?)", ("test.py::case[1]",))
        settle(run.store, 30)
        assert run.store.read("SELECT * FROM cleanup") == []
    finally:
        run.close()


@pytest.mark.parametrize("token_change", [False, True])
def test_cleanup_recovers_same_intent_after_missing_receipt(tmp_path, token_change):
    run, _ = make_run(tmp_path)
    original = run.store
    try:
        add_attempt(run, node="test.py::test_case")
        original.update("UPDATE run SET token_hash='original'")
        settle(original, 30)
        calls = []

        class Client:
            async def submit_cleanup(self, source, targets, key, *, deadline):
                calls.append((source, targets, key))
                if len(calls) == 1:
                    raise LogPlatformError("PLATFORM_NETWORK_ERROR", retryable=True)
                return {"job_id": "same-job"}

        async def db(function, *args):
            return function(*args)

        first = SimpleNamespace(store=original, settings=run.settings, client=Client(), db=db,
                                binding=("url", "original"))
        asyncio.run(submit(first, next_cleanup(original)))
        original.update("UPDATE cleanup SET next_submit=0")
        run_id = original.run()["id"]
        run.close()
        restored = LogRun(tmp_path, run.settings)
        restored.open(run_id, resume=True)
        try:
            first.store = restored.store
            if token_change:
                first.binding = ("url", "different")
            asyncio.run(submit(first, next_cleanup(restored.store)))
            receipt, = restored.store.read("SELECT state,job_id,reason FROM cleanup")
            if token_change:
                assert len(calls) == 1
                assert receipt == {"state": "unknown", "job_id": None, "reason": "TOKEN_CHANGED"}
            else:
                assert calls[0] == calls[1]
                assert receipt == {"state": "accepted", "job_id": "same-job", "reason": None}
        finally:
            restored.close()
    finally:
        run.close()


def test_resume_republishes_old_revision_without_replacing_newer_latest(tmp_path, monkeypatch):
    older, old_path = make_run(tmp_path, "20261119-01")
    add_attempt(older, node="test.py::test_case")
    older.store.update("UPDATE request SET rules='[]'")
    settle(older.store, 30)
    older.store.update("UPDATE run SET state='DRAINING',pytest_exit=0")
    from aitest_kit.log_assertions import run as runner
    with monkeypatch.context() as patch:
        def fail_to_write(*args, **kwargs):
            raise OSError("simulated interrupted final publication")
        patch.setattr(runner, "publish", fail_to_write)
        with pytest.raises(click.ClickException, match="publish"):
            older.finish(0)
    assert older.store.run()["published"] == 0
    older.close()
    newer, new_path = make_run(tmp_path, "20261119-02")
    try:
        add_attempt(newer, node="test.py::test_case")
        newer.store.update("UPDATE request SET rules='[]'")
        settle(newer.store, 30)
        assert publish(newer.store, newer.settings, final=True, prior_code=0) == 0
        latest = new_path.parents[1] / "latest" / "result.json"
        assert json.loads(latest.read_text())["run_id"] == "20261119-02"
    finally:
        newer.close()
    assert resume(tmp_path, "20261119-01", lambda files: {}) == 0
    assert json.loads((old_path / "result.json").read_text())["log_validation"]["final"]
    assert json.loads(latest.read_text())["run_id"] == "20261119-02"


def test_missing_declared_steps_block_a_passing_pytest_case_and_its_cleanup(tmp_path):
    run, _ = make_run(tmp_path)
    try:
        node = "test.py::test_case"
        attempt = add_attempt(run, node=node)
        run.store.update("INSERT INTO declared_step VALUES(0,?,?)", (node, "second_request"))
        settle(run.store, 30)
        assert run.store.read("SELECT outcome FROM settled_case WHERE attempt=?", (attempt,)) == [{"outcome": "error"}]
        assert not run.store.read("SELECT 1 FROM cleanup")
    finally:
        run.close()


def test_final_run_uses_last_attempt_and_retains_earlier_evidence(tmp_path):
    run, path = make_run(tmp_path)
    try:
        node = "test.py::test_case[param]"
        add_attempt(run, node=node, result="FAILED", seal=False)
        add_attempt(run, node=node)
        run.store.update("UPDATE request SET rules='[]'")
        settle(run.store, 30)
        assert run.finish(0) == 0
        case, = json.loads((path / "result.json").read_text())["cases"]
        assert case["nodeid"] == node and case["outcome"] == "passed"
        assert case["log_validation"]["attempt"] == 2
        assert case["attempt_history"][0]["attempt"] == 1
    finally:
        run.close()


def test_mixed_task_keeps_legacy_unit_and_reports_consistent_child_status(tmp_path):
    run, root = make_run(tmp_path)
    try:
        old, new = (root / "units" / name for name in ("01_old", "02_log"))
        old.mkdir(parents=True)
        legacy = {"cases": [{"nodeid": "old.py::test_pass", "outcome": "passed"}], "summary": {},
                  "run_id": "case-run", "status": "COMPLETED"}
        (old / "result.json").write_text(json.dumps(legacy))
        plan = {"root": str(root), "bucket": str(root.parents[1]), "units": [[1, str(old)], [0, str(new)]],
                "base": {"run_id": "case-run", "task": {"units": [{"index": 0, "status": "COMPLETED"}]}}}
        run.store.update("UPDATE report_plan SET payload=?", (json.dumps(plan),))
        save_base(run.store, root, plan["base"])
        save_base(run.store, new, {"summary": {}, "run_id": "case-run"})
        add_attempt(run, node="log.py::test_fail", result="FAILED")
        settle(run.store, 30)
        publish(run.store, run.settings)
        assert publish(run.store, run.settings, final=True, prior_code=0) == 1
        final = json.loads((root / "result.json").read_text())
        assert final["summary"]["passed"] == final["summary"]["failed"] == 1
        assert final["task"]["units"][1]["status"] == json.loads((new / "result.json").read_text())["status"]
        assert not final["log_validation"]["issues"]
    finally:
        run.close()


def test_failed_comparison_does_not_persist_sensitive_numeric_operand():
    from aitest_kit.log_assertions.rules import evaluate_request
    rules = [{"checks": ['assert events[0]["data"].get("password") == 0']}]
    result = evaluate_request(rules, [{"data": {"password": 717172}}], [{}])
    assert result["state"] == "FAILED"
    assert "717172" not in json.dumps(result)
    assert "password" not in json.dumps(result)


def test_resume_initializes_cleanup_credentials_before_new_intents(tmp_path, monkeypatch):
    from aitest_kit.log_assertions.coordinator import Coordinator
    calls = []

    async def credentials(self, env):
        calls.append(env)
        self.binding = ("url", "original")

        async def submit_cleanup(*args, **kwargs):
            return {"job_id": "accepted"}

        self.client = SimpleNamespace(submit_cleanup=submit_cleanup, aclose=aclose)
        return self.client

    async def aclose():
        pass

    monkeypatch.setattr(Coordinator, "credentials", credentials)
    run, _ = make_run(tmp_path)
    add_attempt(run, node="log.py::test_pass")
    run.store.update("UPDATE run SET state='DRAINING',pytest_exit=0,token_hash='original'")
    run.close()
    # Bound the broken-path wait as well.
    from aitest_kit.log_assertions import coordinator
    original = coordinator.settle
    monkeypatch.setattr(coordinator, "settle", lambda store, budget: original(store, .35))
    assert resume(tmp_path, "case-run", lambda files: {"fixture": "loaded"}) == 0
    assert calls == [{"fixture": "loaded"}]
    assert run.store.read("SELECT state FROM cleanup") == [{"state": "accepted"}]


def test_cancelled_recovery_settles_interrupted_cleanup_transition(tmp_path):
    run, root = make_run(tmp_path)
    add_attempt(run, node="log.py::test_pass")
    settle(run.store, 30)
    run.store.update("UPDATE run SET state='CANCELLED',exit_code=2")
    run.close()
    assert resume(tmp_path, "case-run", lambda _: {}) == 2
    request = json.loads((root / "result.json").read_text())["cases"][0]["log_validation"]["requests"][0]
    assert request["cleanup"]["state"] == "failed"
    assert request["cleanup"]["reason"] == "CANCELLED"


def test_latest_publication_failure_keeps_a_complete_previous_report(tmp_path, monkeypatch):
    from aitest_kit.report import publication
    from pathlib import Path
    bucket = tmp_path / "reports"
    runs = bucket / "runs"
    for name in ("01", "02"):
        publication.write_report(runs / name, {"run_id": name}, f"<testsuite name='{name}'/>".encode())
    publication.update_latest(runs / "01", bucket, {"run_id": "01"})
    replace = publication.os.replace

    def fail_switch(source, target):
        if Path(target) in (bucket / "latest", bucket / "latest" / "result.json"):
            raise OSError("simulated publication failure")
        replace(source, target)

    monkeypatch.setattr(publication.os, "replace", fail_switch)
    with pytest.raises(OSError, match="simulated"):
        publication.update_latest(runs / "02", bucket, {"run_id": "02"})
    latest = bucket / "latest"
    if not latest.exists():
        latest = bucket / ".latest-previous"
    assert json.loads((latest / "result.json").read_text())["run_id"] == "01"
    assert "01" in (latest / "report.md").read_text()
    assert "'01'" in (latest / "junit.xml").read_text()


def test_ready_cleanup_queue_does_not_wait_between_submissions(tmp_path, monkeypatch):
    from aitest_kit.log_assertions.coordinator import Coordinator

    async def credentials(self, env):
        async def submit_cleanup(*args, **kwargs):
            return {"job_id": "accepted"}

        async def aclose():
            pass

        self.binding = ("url", "original")
        self.client = SimpleNamespace(submit_cleanup=submit_cleanup, aclose=aclose)
        return self.client

    monkeypatch.setattr(Coordinator, "credentials", credentials)
    run, _ = make_run(tmp_path)
    try:
        for index in range(12):
            add_attempt(run, node=f"log.py::test_{index}")
        run.store.update("UPDATE run SET token_hash='original'")
        settle(run.store, .75)
        run.start({"fixture": "loaded"})
        assert run.finish(0) == 0
        assert run.store.read("SELECT state, COUNT(*) AS total FROM cleanup GROUP BY state") == [
            {"state": "accepted", "total": 12}
        ]
    finally:
        run.close()


def test_resume_multiple_cleanup_units_without_platform_credentials(tmp_path):
    run, path = make_run(tmp_path)
    run.store.update("INSERT INTO unit VALUES(?,?,?,?)", (1, str(path), "[]", '["second.env"]'))
    first = add_attempt(run, node="test.py::first")
    second = add_attempt(run, node="test.py::second")
    run.store.update("UPDATE attempt SET unit=1 WHERE id=?", (second,))
    run.store.update("UPDATE case_closed SET unit=1 WHERE nodeid=?", ("test.py::second",))
    run.store.update("UPDATE run SET state='DRAINING',pytest_exit=0")
    settle(run.store, 30)
    assert first != second and len(run.store.read("SELECT * FROM cleanup WHERE state='queued'")) == 2
    run.close()
    resume(tmp_path, "case-run", lambda files: {})
    assert run.store.read("SELECT state,reason FROM cleanup ORDER BY request") == [
        {"state": "unknown", "reason": "ORIGINAL_TOKEN_UNAVAILABLE"},
        {"state": "unknown", "reason": "ORIGINAL_TOKEN_UNAVAILABLE"},
    ]
