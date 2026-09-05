from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from aitest_kit.console.agent_event_log import AgentEventLog
from aitest_kit.console.agent_session_store import AgentSessionStore
from aitest_kit.console.errors import ConsoleError


def test_session_store_is_workspace_scoped_and_archival_is_recoverable(tmp_path: Path) -> None:
    store = AgentSessionStore(tmp_path / "sessions")
    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    workspace_a.mkdir()
    workspace_b.mkdir()

    record = store.create(workspace_a, "approval")
    record.title = "检查订单用例"
    store.save(record)

    assert [item.session_id for item in store.list(workspace_a)] == [record.session_id]
    assert store.list(workspace_b) == []
    assert store.load(workspace_a, record.session_id).title == "检查订单用例"

    store.archive(workspace_a, record.session_id)

    assert store.list(workspace_a) == []
    assert store.load(workspace_a, record.session_id, include_archived=True).archived is True
    assert (store.session_dir(workspace_a, record.session_id) / "meta.json").exists()
    assert stat.S_IMODE(store.root.stat().st_mode) == 0o700
    assert stat.S_IMODE(store.workspace_dir(workspace_a).stat().st_mode) == 0o700
    assert stat.S_IMODE(store.session_dir(workspace_a, record.session_id).stat().st_mode) == 0o700
    assert stat.S_IMODE((store.session_dir(workspace_a, record.session_id) / "meta.json").stat().st_mode) == 0o600


def test_session_store_isolates_one_corrupt_record(tmp_path: Path, caplog) -> None:
    store = AgentSessionStore(tmp_path / "sessions")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    valid = store.create(workspace, "approval")
    corrupt = store.create(workspace, "approval")
    (store.session_dir(workspace, corrupt.session_id) / "meta.json").write_text("not json", encoding="utf-8")

    records = store.list(workspace)

    assert [record.session_id for record in records] == [valid.session_id]
    assert "Ignoring invalid Agent session metadata" in caplog.text


def test_session_store_rejects_pi_file_outside_its_pi_directory(tmp_path: Path) -> None:
    store = AgentSessionStore(tmp_path / "sessions")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    record = store.create(workspace, "approval")
    outside = store.session_dir(workspace, record.session_id) / "meta.json"

    with pytest.raises(ConsoleError) as error:
        store.set_pi_session_file(record, str(outside))

    assert getattr(error.value, "code", None) == "AGENT_SESSION_PATH_INVALID"


def test_persistent_event_log_restores_seq_and_removes_live_diff_content(tmp_path: Path) -> None:
    journal = tmp_path / "events.jsonl"
    log = AgentEventLog(journal_path=journal)
    log.append("session-1", "user_message", {"text": "你好"})
    log.append(
        "session-1",
        "tool_call_requested",
        {
            "tool_call_id": "tool-1",
            "tool_name": "edit",
            "input": {
                "path": "suite.md",
                "old_text": "secret old content",
                "new_text": "secret new content",
            },
        },
    )
    log.append(
        "session-1",
        "tool_call_updated",
        {"tool_call_id": "tool-2", "tool_name": "bash", "partial_result": {"output": "private stream output"}},
    )
    log.append(
        "session-1",
        "tool_call_finished",
        {"tool_call_id": "tool-2", "tool_name": "bash", "is_error": False, "result": {"output": "private final output"}},
    )

    restored = AgentEventLog(journal_path=journal)
    next_event = restored.append("session-1", "agent_finished", {"status": "succeeded"})
    persisted = journal.read_text(encoding="utf-8")

    assert restored.replay(0).events[0]["payload"]["text"] == "你好"
    assert next_event["seq"] == 5
    assert "secret old content" not in persisted
    assert "secret new content" not in persisted
    assert "private stream output" not in persisted
    assert "private final output" not in persisted
    assert '"path":"suite.md"' in persisted


def test_event_log_ignores_only_an_incomplete_final_line(tmp_path: Path) -> None:
    journal = tmp_path / "events.jsonl"
    first = {
        "event_id": "event-1",
        "seq": 1,
        "session_id": "session-1",
        "type": "user_message",
        "timestamp": "2026-09-01T00:00:00Z",
        "correlation_id": "",
        "payload": {"text": "hello"},
    }
    journal.write_text(json.dumps(first) + "\n{\"event_id\":", encoding="utf-8")

    restored = AgentEventLog(journal_path=journal)

    assert restored.last_seq == 1
    assert restored.replay(0).events == [first]


@pytest.mark.parametrize('tail', [b'{"seq":2', b'{"text":"\xe4\xbd', b''])
def test_event_log_can_append_after_recovering_tail(tmp_path: Path, tail: bytes) -> None:
    journal = tmp_path / 'events.jsonl'
    log = AgentEventLog(journal_path=journal)
    log.append('s', 'text_delta', {'delta': '你好'})
    initial = journal.read_bytes().rstrip(b'\n') if not tail else journal.read_bytes() + tail
    journal.write_bytes(initial)
    restored = AgentEventLog(journal_path=journal)
    assert journal.read_bytes() == initial  # Loading history is read-only.
    restored.append('s', 'agent_finished', {'status': 'succeeded'})
    reopened = AgentEventLog(journal_path=journal)
    assert [event['seq'] for event in reopened.replay(0).events] == [1, 2]


def test_failed_persistence_does_not_advance_event_seq(tmp_path: Path, monkeypatch) -> None:
    log = AgentEventLog(journal_path=tmp_path / 'events.jsonl')
    def fail(_event):
        raise OSError('disk full')
    monkeypatch.setattr(log, '_persist', fail)
    with pytest.raises(OSError, match='disk full'):
        log.append('s', 'text_delta', {'delta': 'hello'})
    assert log.last_seq == 0
    assert log.replay(0).events == []
