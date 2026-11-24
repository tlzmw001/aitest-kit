"""Regression cases for deferred-run scheduling and restart."""
import asyncio
from threading import Event, Thread
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import click
import pytest

from aitest_kit.log_assertions.config import RunSettings, load_settings
from aitest_kit.log_assertions.coordinator import Coordinator
from aitest_kit.log_assertions.run import LogRun, log_run, resume
from aitest_kit.log_assertions.store import RunStore


def register(run, *, static=True, deadline=None):
    store = run.store
    attempt = store.start_attempt(0, 'test.py::test_call', 'main')
    expected = {'literal': 1} if static else {'from_response': '/score'}
    request = store.register(attempt, 'call', 'demo', [
        {'expected': {'score': expected}, 'executor_version': 1}
    ], [{'score': 1} if static else {}], deadline or time.time() + 120, 5)
    store.bind(request, 'call-1')
    return attempt, request


@pytest.fixture
def run(tmp_path):
    session = LogRun(tmp_path, RunSettings())
    session.open('regression')
    session.store.update('INSERT INTO unit VALUES(?,?,?,?)', (0, str(tmp_path), '[]', '[]'))
    try:
        yield session
    finally:
        session.close()


def test_drain_observes_requests_registered_after_empty_read(run, monkeypatch):
    reached, release = Event(), Event()
    original = run.store.read

    def read(sql, *args):
        rows = original(sql, *args)
        if 'FROM request WHERE state IN' in sql and not rows and not reached.is_set():
            reached.set()
            assert release.wait(5)
        return rows

    monkeypatch.setattr(run.store, 'read', read)
    run.start()
    assert reached.wait(5)
    attempt, request = register(run, deadline=time.time() - 1)
    run.store.freeze(request, [{'score': 1}])
    run.store.phase(attempt, 'teardown', 'passed')
    exits = []
    finisher = Thread(target=lambda: exits.append(run.finish(0)))
    finisher.start()
    assert run.draining.wait(5)
    release.set()
    finisher.join(5)
    assert exits == [1]
    assert original('SELECT state FROM request') == [{'state': 'ERROR'}]


def test_explicit_serial_rejects_xdist_for_legacy_suite(tmp_path, monkeypatch):
    file = tmp_path / 'test_old.py'
    file.write_text('def test_old(): pass\n')
    from aitest_kit.log_assertions import run as runner
    monkeypatch.setattr(runner.subprocess, 'run', lambda *a, **k: None)
    with log_run(tmp_path, 1, None, {}) as session:
        with pytest.raises(click.ClickException, match='distributed options'):
            session.execute([], {}, [file], tmp_path, 'serial', [], ['-n', '2'], [], 0)


@pytest.mark.parametrize('static,expected', [(True, 'WAITING'), (False, 'ERROR')])
def test_recover_bound_request_uses_durable_inputs(run, static, expected):
    register(run, static=static)
    run.store.recover()
    assert run.store.read('SELECT state FROM request') == [{'state': expected}]


def test_resume_settles_expired_waiter_without_credentials(run):
    attempt, request = register(run, deadline=time.time() - 60)
    run.store.freeze(request, [{'score': 1}])
    run.store.phase(attempt, 'teardown', 'passed')
    run.store.update("UPDATE run SET state='DRAINING',pytest_exit=0")
    run.close()
    assert resume(run.workspace, 'regression', lambda files: {}) == 1
    assert RunStore(run.store.path).read('SELECT state FROM request') == [{'state': 'ERROR'}]


def test_poll_rotates_across_sources_even_with_different_deadlines():
    async def scenario():
        coordinator = Coordinator(SimpleNamespace(observe=Mock()), RunSettings(), {}, Event(), Event())
        sources = []

        async def statuses(source, ids, **kwargs):
            sources.append(source)
            return [{'request': None, 'result': 'NOT_FOUND'}]

        coordinator.client = SimpleNamespace(batch_size=1, readiness_batch_supported=False, get_statuses=statuses)
        now = time.time()
        rows = [{'source': source, 'id': rank, 'correlation': source, 'deadline': now + 30 + rank,
                 'expires': None} for rank, source in enumerate(('a', 'z', 'b'))]
        for _ in rows:
            await coordinator.poll(rows)
        coordinator.executor.shutdown()
        return sources

    assert asyncio.run(scenario()) == ['a', 'b', 'z']


@pytest.mark.parametrize("value", [
    "null", "''", "42", "bridge.invalid:8000", "http://user:secret@bridge.invalid",
    "http://bridge.invalid/?", "http://bridge.invalid/#", "http://bridge.invalid:65536",
])
def test_yaml_rejects_invalid_platform_url_without_echoing_it(tmp_path, value):
    config = tmp_path / "aitest_config"
    config.mkdir()
    (config / "log_assertions.yaml").write_text(f"platform:\n  base_url: {value}\n")
    with pytest.raises(ValueError, match="platform.base_url") as error:
        load_settings(tmp_path)
    assert "secret" not in str(error.value)


def test_platform_address_is_workspace_local_and_normalized(tmp_path):
    env = {"AITEST_LOG_BASE_URL": "http://legacy.invalid/service", "AITEST_LOG_TOKEN": "fixture"}
    for name, port in (("first", 41001), ("second", 41002)):
        workspace = tmp_path / name
        config = workspace / "aitest_config"
        config.mkdir(parents=True)
        url = f"http://bridge.invalid:{port}/service%2Flogs"
        (config / "log_assertions.yaml").write_text(f"platform:\n  base_url: {url}\n")
        assert load_settings(workspace).platform_credentials(env) == (url + "/", "fixture")
    assert load_settings(tmp_path).platform_credentials(env) == ("http://legacy.invalid/service/", "fixture")


def test_saved_env_address_cannot_redirect_resume(run):
    from hashlib import sha256

    async def scenario():
        coordinator = Coordinator(run.store, run.settings, {}, Event(), Event())
        run.store.update("UPDATE run SET url_hash=?", (sha256(b"http://old.invalid/logs/").hexdigest(),))
        try:
            with pytest.raises(ValueError, match="differs from the saved run"):
                await coordinator.credentials({"AITEST_LOG_BASE_URL": "http://new.invalid/logs",
                                               "AITEST_LOG_TOKEN": "fixture"})
            assert coordinator.client is None
        finally:
            coordinator.executor.shutdown()

    asyncio.run(scenario())


def test_mixed_poll_batches_same_id_across_sources_and_reduces_limit():
    async def scenario():
        from aitest_kit.log_assertions.client import LogPlatformError

        coordinator = Coordinator(SimpleNamespace(observe=Mock()), RunSettings(), {}, Event(), Event())
        readiness = AsyncMock(side_effect=[
            LogPlatformError("TOO_MANY_TARGETS", status=422, limit=1), [{"request": None, "result": "NOT_FOUND"}],
        ])
        coordinator.client = SimpleNamespace(batch_size=2, readiness_batch_supported=True, get_readiness=readiness)
        now = time.time()
        rows = [{"source": source, "id": rank, "correlation": "shared", "deadline": now + 30 + rank,
                 "expires": None} for rank, source in enumerate(("a", "b"))]
        try:
            await coordinator.poll(rows)
            coordinator.store.observe.assert_not_called()
            await coordinator.poll(rows)
        finally:
            coordinator.executor.shutdown()
        assert [call.args[0] for call in readiness.await_args_list] == [
            [("a", "shared"), ("b", "shared")], [("a", "shared")],
        ]
        coordinator.store.observe.assert_called_once()

    asyncio.run(scenario())


def test_cancel_preflight_without_starting_other_platform_calls(run):
    started = Event()
    calls = []
    for key in ('first', 'second'):
        run.store.update('INSERT INTO preflight(id,unit,sources) VALUES(?,0,?)', (key, '{}'))
    run.environments[0] = {}
    coordinator = Coordinator(run.store, run.settings, run.environments, run.draining, run.stopping)

    async def preflight(row, env):
        calls.append(row['id'])
        started.set()
        await asyncio.sleep(1)

    coordinator.preflight = preflight
    worker = Thread(target=lambda: asyncio.run(coordinator.run()))
    worker.start()
    assert started.wait(5)
    run.stopping.set()
    worker.join(5)
    assert not worker.is_alive()
    assert calls == ['first']


def test_retention_advances_past_first_batch(tmp_path):
    from dataclasses import asdict
    from aitest_kit.log_assertions.run import reclaim_published

    for index in range(102):
        folder = tmp_path / f"run-{index:03}"
        folder.mkdir()
        store = RunStore(folder / "log-assertions.sqlite3")
        store.create(folder.name, tmp_path, asdict(RunSettings()), {})
        if index == 101:
            store.update("UPDATE run SET state='FINISHED',published=1,finished=1")
    reclaim_published(tmp_path, 10)
    assert store.path.exists()
    reclaim_published(tmp_path, 10)
    assert not store.path.exists()


def test_waiting_queue_loads_only_scheduling_fields(run, monkeypatch):
    started = Event()
    run.store.update("UPDATE run SET state='RUNNING'")
    _, request = register(run)
    run.store.freeze(request, [{'score': 1}])
    run.store.update('UPDATE request SET next_poll=?', (time.time() + 60,))
    read = run.store.read
    found = []

    def observe(sql, *args):
        rows = read(sql, *args)
        if "FROM request WHERE state IN" in sql:
            found.extend(rows)
            started.set()
            run.stopping.set()
        return rows

    monkeypatch.setattr(run.store, 'read', observe)
    run.start()
    assert started.wait(5)
    run.thread.join(5)
    assert found[0]["id"] == request
    assert {"rules", "inputs"}.isdisjoint(found[0])


def test_resume_finished_run_ignores_current_platform_settings(run):
    config = run.workspace / "aitest_config"
    config.mkdir()
    (config / "log_assertions.yaml").write_text("platform:\n  base_url: null\n")
    run.store.update("UPDATE run SET state='FINISHED',published=1,exit_code=0")
    run.close()

    def load_env(files):
        pytest.fail("finished run must not load platform credentials")

    assert resume(run.workspace, "regression", load_env) == 0


def test_legacy_url_binding_is_rehashed_only_with_original_token(run):
    import hashlib
    import hmac
    import json

    original = run.store.run()
    settings = json.loads(original["settings"])
    settings.pop("base_url")
    token = "fixture"
    fingerprint = hmac.new(bytes.fromhex(original["salt"]), token.encode(), hashlib.sha256).hexdigest()
    run.store.update("UPDATE run SET settings=?,url_hash=?,token_hash=?", (
        json.dumps(settings), hashlib.sha256(b"http://old.invalid/a/b/").hexdigest(), fingerprint,
    ))
    env = {"AITEST_LOG_BASE_URL": "http://old.invalid/a%2Fb", "AITEST_LOG_TOKEN": token}

    async def scenario():
        coordinator = Coordinator(run.store, run.settings, {}, Event(), Event())
        try:
            with pytest.raises(ValueError, match="differs from the saved run"):
                await coordinator.credentials({**env, "AITEST_LOG_TOKEN": "different"})
            await coordinator.credentials(env)
            saved = run.store.run()
            assert saved["url_hash"] == hashlib.sha256(b"http://old.invalid/a%2Fb/").hexdigest()
            assert "base_url" in json.loads(saved["settings"])
        finally:
            if coordinator.client:
                await coordinator.client.aclose()
            coordinator.executor.shutdown()

    asyncio.run(scenario())


def test_mixed_poll_gives_overdue_peers_a_turn(run, monkeypatch):
    async def scenario():
        store = run.store
        attempt = store.start_attempt(0, "case", "main")
        now = time.time()
        handle = store.register(attempt, "reply", "anchor",
                                [{"source_id": "a"}, {"source_id": "b"}], [{}, {}], now + 20, 2)
        store.bind(handle, "shared")
        store.freeze(handle, [{}, {}])
        readiness = AsyncMock(return_value=[{"request": None, "result": "NOT_FOUND"}])
        coordinator = Coordinator(store, run.settings, {}, Event(), Event())
        coordinator.client = SimpleNamespace(readiness_batch_supported=True, batch_size=1, get_readiness=readiness)
        try:
            for stamp in (now + 1, now + 3):
                monkeypatch.setattr(time, "time", lambda: stamp)
                await coordinator.poll(store.read("SELECT * FROM request WHERE next_poll<=? ORDER BY source", (stamp,)))
        finally:
            coordinator.executor.shutdown()
        assert [call.args[0] for call in readiness.await_args_list] == [[("a", "shared")], [("b", "shared")]]

    asyncio.run(scenario())


def test_readiness_batches_ninety_source_pairs_and_leaves_only_pending(run):
    import json
    import httpx
    from aitest_kit.log_assertions.client import LogPlatformClient

    async def scenario():
        store = run.store
        now = time.time()
        calls = []

        def platform(request):
            assert request.url.path == "/v1/requests/readiness"
            pairs = json.loads(request.content)["items"]
            calls.append(pairs)
            return httpx.Response(200, json={"items": [
                {**pair, "result": "FOUND", "request": {
                    **pair, "capture_state": "COLLECTING" if pair["source_id"] == "lake" else "COMPLETE",
                    "availability": "AVAILABLE", "version": 1, "event_count": 1,
                }}
                for pair in pairs
            ]})

        for index in range(30):
            attempt = store.start_attempt(0, f"case-{index}", "main")
            rules = [{"source_id": source} for source in ("main", "perf", "lake")]
            handle = store.register(attempt, "reply", "main", rules, [{}, {}, {}], now + 20, 100)
            store.bind(handle, f"id-{index}")
            store.freeze(handle, [{}, {}, {}])
        coordinator = Coordinator(store, run.settings, {}, Event(), Event())
        async with LogPlatformClient("http://test.invalid", "fixture", transport=httpx.MockTransport(platform)) as client:
            client.readiness_batch_supported = True
            coordinator.client = client
            try:
                for _ in range(2):
                    await coordinator.poll(store.read("SELECT * FROM request WHERE state='WAITING'"))
            finally:
                coordinator.executor.shutdown()
        assert [len(batch) for batch in calls] == [90, 30]
        assert {row["source_id"] for row in calls[1]} == {"lake"}
        assert len({(row["source_id"], row["reqId"]) for row in calls[0]}) == 90

    asyncio.run(scenario())
