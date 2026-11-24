import asyncio
import json
from threading import Event
from types import SimpleNamespace

import httpx
import pytest

from aitest_kit.log_assertions.client import LogPlatformClient, LogPlatformError
from aitest_kit.log_assertions.projection import project_request
from aitest_kit.log_assertions.rules import evaluate_request


def test_snapshot_decode_cannot_accept_an_expired_page(monkeypatch):
    from aitest_kit.log_assertions import client

    async def scenario():
        loop = asyncio.get_running_loop()
        release = Event()
        started = asyncio.Event()
        original = json.loads

        def decode(*args, **kwargs):
            loop.call_soon_threadsafe(started.set)
            release.wait(.5)
            return original(*args, **kwargs)

        page = {
            "request": {"source_id": "main", "reqId": "id", "capture_state": "COMPLETE",
                        "availability": "AVAILABLE", "event_count": 0, "version": 1},
            "upper_offset": None, "items": [], "next_cursor": None,
        }
        monkeypatch.setattr(client.json, "loads", decode)
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json=page))
        async with LogPlatformClient("http://fixture.invalid", "fixture", transport=transport) as platform:
            task = asyncio.create_task(platform.read_snapshot("main", "id", 1, deadline=loop.time() + .1))
            try:
                await asyncio.wait_for(started.wait(), 2)
                with pytest.raises(LogPlatformError, match="DEADLINE_EXCEEDED"):
                    await task
            finally:
                release.set()

    asyncio.run(scenario())


def test_unexecuted_sensitive_check_is_redacted_and_evidence_includes_partition():
    rules = [{"checks": ["assert False", 'assert events[0]["data"]["cookie"] == "fixture-marker"']}]
    events = [{"event_id": "a", "partition": 2, "offset": "1"}, {"event_id": "b", "partition": 3, "offset": "1"}]
    result = evaluate_request(rules, events, [{}])
    row = {"payload": json.dumps(result), "rules": json.dumps(rules), "semantics": 2,
           "state": "FAILED", "step": "reply", "source": "perf", "correlation": "id",
           "version": 1, "cleanup_state": None, "job_id": None, "reason": None}
    projected = project_request(row, "failed", "TC-1")
    assert projected["rules"][1]["result"] == "not_run"
    assert projected["rules"][1]["expression"] == "[REDACTED]"
    assert projected["rules"][0]["evidence"] == [{"event_id": "a", "partition": 2, "offset": "1"}]


def test_cleanup_backlog_gets_a_submission_budget(tmp_path):
    from test_cleanup_projection import add_attempt, make_run
    from aitest_kit.log_assertions.cleanup import settle, submit_available

    async def scenario():
        run, _ = make_run(tmp_path)
        release = asyncio.Event()
        started = asyncio.Event()
        in_flight = set()
        peak = 0

        async def submit_cleanup(source, ids, key, *, deadline):
            nonlocal peak
            assert deadline > asyncio.get_running_loop().time()
            assert ids[0] not in in_flight
            in_flight.add(ids[0])
            peak = max(peak, len(in_flight))
            if peak == 4:
                started.set()
            await release.wait()
            in_flight.remove(ids[0])
            return {"job_id": key}

        async def db(function, *args):
            return function(*args)

        try:
            for i in range(30):
                add_attempt(run, node=f"test.py::test_{i}")
            run.store.update("UPDATE run SET token_hash='fixture'")
            settle(run.store, run.settings.queue_timeout_seconds)
            run.store.update("UPDATE cleanup SET deadline=deadline-16,next_submit=0")
            coordinator = SimpleNamespace(store=run.store, db=db, settings=run.settings, binding=("url", "fixture"),
                                          stopping=Event(), client=SimpleNamespace(submit_cleanup=submit_cleanup))
            submission = asyncio.create_task(submit_available(coordinator))
            try:
                await asyncio.wait_for(started.wait(), 2)
            finally:
                release.set()
                await submission
            assert peak == 4
            assert run.store.read("SELECT COUNT(*) AS total FROM cleanup WHERE state='accepted'") == [{"total": 30}]
        finally:
            run.close()

    asyncio.run(scenario())


def test_cleanup_only_resume_settles_when_saved_env_file_disappears(tmp_path):
    from click.testing import CliRunner
    from test_cleanup_projection import add_attempt, make_run
    from aitest_kit.cli import main
    from aitest_kit.log_assertions.cleanup import settle

    run, path = make_run(tmp_path)
    add_attempt(run, node="test.py::test_pass")
    run.store.update("UPDATE unit SET env_files=?", (json.dumps([str(tmp_path / "missing.env")]),))
    run.store.update("UPDATE run SET state='DRAINING',pytest_exit=0,token_hash='fixture'")
    settle(run.store, 30)
    run.close()
    result = CliRunner().invoke(main, ["run", "--workspace", str(tmp_path), "--resume", "case-run"])
    assert result.exit_code == 1
    report = json.loads((path / "result.json").read_text())
    assert report["summary"]["passed"] == 1
    assert report["log_validation"]["final"]
    assert report["log_validation"]["issues"][0]["reason"] == "ORIGINAL_TOKEN_UNAVAILABLE"


def test_blocked_child_preserves_exit_code_and_junit_error(tmp_path):
    from test_cleanup_projection import make_run
    from aitest_kit.log_assertions.projection import publish, save_base

    run, root = make_run(tmp_path)
    try:
        child = root / "units" / "blocked"
        base = {"run_id": "case-run"}
        plan = {"root": str(root), "bucket": str(root.parents[1]), "units": [[0, str(child)]], "base": base}
        run.store.update("UPDATE report_plan SET payload=?", (json.dumps(plan),))
        save_base(run.store, child, {**base, "status": "BLOCKED_RUN", "blocked_reason": "codegen_check"})
        assert publish(run.store, run.settings, final=True, prior_code=10) == 10
        report = json.loads((child / "result.json").read_text())
        assert report["status"] == "BLOCKED_RUN"
        assert report["log_validation"]["exit_code"] == 10
        assert 'errors="1"' in (child / "junit.xml").read_text()
    finally:
        run.close()
