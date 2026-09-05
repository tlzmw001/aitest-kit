from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from aitest_kit.agent.protocol import ProtocolMessage
from aitest_kit.agent.client import WorkerClient
from aitest_kit.console.agent_event_log import AgentEventLog
from aitest_kit.console.agent_session_api import _stream_events
from aitest_kit.console.errors import ConsoleError
from tests.console.test_console_agent_sessions import _manager


@pytest.mark.parametrize('operation', ['list', 'get', 'history', 'activate', 'archive'])
def test_other_console_never_recovers_a_live_owner(console_workspace: Path, tmp_path: Path, operation: str) -> None:
    home = tmp_path / 'sessions'
    owner, _ = _manager(console_workspace, home)
    visitor, _ = _manager(console_workspace, home)
    created = owner.create('approval', confirmed=False)
    session_id = created['session_id']
    session = owner.require(session_id)
    try:
        # Synchronous worker event avoids timing assumptions about the reader.
        session._handle_worker_event(ProtocolMessage.create('permission_requested', {
            'request_id': 'pending', 'tool_name': 'bash', 'surface': 'bash', 'command': 'git status',
        }))
        path = owner._store.event_path(console_workspace, session_id)
        before = path.read_bytes()
        if operation in {'archive', 'activate'}:
            with pytest.raises(ConsoleError) as caught:
                visitor.archive(session_id) if operation == 'archive' else visitor.activate(session_id, confirmed=False)
            assert caught.value.code == 'AGENT_WORKER_ALREADY_ACTIVE'
        elif operation == 'list':
            assert visitor.list_sessions()[0]['status'] == 'awaiting_approval'
        elif operation == 'get':
            assert visitor.get(session_id)['status'] == 'awaiting_approval'
        else:
            visitor.history(session_id, after_seq=0)
        assert path.read_bytes() == before
        session._handle_worker_event(ProtocolMessage.create('text_delta', {'delta': 'still alive'}))
        restored = AgentEventLog(journal_path=path)
        assert restored.last_seq == session.events.last_seq
    finally:
        owner.close()
        visitor.close()


def test_partial_session_start_failure_cleans_worker_before_lease_release(console_workspace: Path, tmp_path: Path, monkeypatch) -> None:
    manager, worker = _manager(console_workspace, tmp_path / 'sessions')
    def fail(*args):
        raise OSError('metadata write failed')
    monkeypatch.setattr(manager._store, 'set_pi_session_file', fail)
    try:
        with pytest.raises(OSError, match='metadata write failed'):
            manager.create('approval', confirmed=False)
        assert worker.closed is True
        assert manager.snapshot() is None
        lease = manager._store.worker_lease(console_workspace)
        lease.acquire()
        lease.release()
    finally:
        manager.close()


def test_missing_executable_preserves_start_error_and_releases_lease(console_workspace: Path, tmp_path: Path) -> None:
    manager, _ = _manager(console_workspace, tmp_path / 'sessions')
    manager._worker_factory = lambda env: WorkerClient([str(tmp_path / 'missing-worker')])
    with pytest.raises(ConsoleError) as caught:
        manager.create('approval', confirmed=False)
    assert caught.value.code == 'WORKER_START_FAILED'
    lease = manager._store.worker_lease(console_workspace)
    lease.acquire()
    lease.release()


def test_active_history_has_snapshot_at_same_seq(console_workspace: Path, tmp_path: Path) -> None:
    manager, _ = _manager(console_workspace, tmp_path / 'sessions')
    created = manager.create('approval', confirmed=False)
    try:
        history = manager.history(created['session_id'], after_seq=0)
        assert history['session']['last_seq'] == history['last_seq']
    finally:
        manager.close()


def test_resync_keeps_window_and_pending_approval_outside_window(console_workspace: Path, tmp_path: Path) -> None:
    manager, _ = _manager(console_workspace, tmp_path / 'sessions')
    created = manager.create('approval', confirmed=False)
    session = manager.require(created['session_id'])
    session._handle_worker_event(ProtocolMessage.create('permission_requested', {
        'request_id': 'pending', 'tool_name': 'bash', 'surface': 'bash', 'command': 'git status',
    }))
    # Use the same bounded log, without fsync for this purely replay-focused test.
    session.events._journal_path = None
    for _ in range(1005):
        session.events.append(session.session_id, 'text_delta', {'delta': 'retained'})
    class Request:
        async def is_disconnected(self):
            return True
    async def receive():
        return [chunk async for chunk in _stream_events(session, Request(), 0)]
    try:
        chunks = asyncio.run(receive())
        payload = json.loads(chunks[0].split('data: ', 1)[1])['payload']
        assert len(payload['events']) == 1000
        assert payload['pending_approvals'][0]['command'] == 'git status'
        assert payload['session']['last_seq'] == payload['events'][-1]['seq']
    finally:
        manager.close()


def test_stream_resyncs_when_window_overflows_after_initial_replay(console_workspace: Path, tmp_path: Path) -> None:
    manager, _ = _manager(console_workspace, tmp_path / 'sessions')
    created = manager.create('approval', confirmed=False)
    session = manager.require(created['session_id'])
    session.events._journal_path = None
    class Request:
        async def is_disconnected(self):
            return False
    async def receive():
        stream = _stream_events(session, Request(), 0)
        try:
            first = json.loads((await stream.__anext__()).split('data: ', 1)[1])
            assert first['type'] == 'session_created'
            for _ in range(1005):
                session.events.append(session.session_id, 'text_delta', {'delta': 'retained'})
            resync = json.loads((await stream.__anext__()).split('data: ', 1)[1])
            assert resync['type'] == 'resync_required'
            assert len(resync['payload']['events']) == 1000
            assert resync['seq'] == session.events.last_seq
        finally:
            await stream.aclose()
    try:
        asyncio.run(receive())
    finally:
        manager.close()


def test_orphaned_running_record_recovers_once_under_free_lease(console_workspace: Path, tmp_path: Path) -> None:
    manager, _ = _manager(console_workspace, tmp_path / 'sessions')
    record = manager._store.create(console_workspace, 'approval')
    record.status = 'running'
    record.active_prompt = True
    manager._store.save(record)
    assert manager.get(record.session_id)['status'] == 'interrupted'
    manager.list_sessions()
    history = manager.history(record.session_id, after_seq=0)
    assert [event['type'] for event in history['events']] == ['session_interrupted']
