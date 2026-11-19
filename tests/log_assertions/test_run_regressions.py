"""Regression cases for deferred-run scheduling and restart."""
import asyncio
from threading import Event, Thread
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import click
import pytest

from aitest_kit.log_assertions.config import RunSettings
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
        coordinator = Coordinator(None, RunSettings(), {}, Event(), Event())
        coordinator.again = AsyncMock()
        sources = []

        async def statuses(source, ids, **kwargs):
            sources.append(source)
            return [{'request': None}]

        coordinator.client = SimpleNamespace(batch_size=1, get_statuses=statuses)
        now = time.time()
        rows = [{'source': source, 'id': rank, 'correlation': source, 'deadline': now + 30 + rank,
                 'expires': None} for rank, source in enumerate(('a', 'z', 'b'))]
        for _ in rows:
            await coordinator.poll(rows)
        coordinator.executor.shutdown()
        return sources

    assert asyncio.run(scenario()) == ['a', 'b', 'z']


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
