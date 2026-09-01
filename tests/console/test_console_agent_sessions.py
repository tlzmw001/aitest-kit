from __future__ import annotations

import queue
import time
from pathlib import Path

from fastapi.testclient import TestClient

from aitest_kit.agent.client import AgentWorkerError
from aitest_kit.agent.protocol import ProtocolMessage
from aitest_kit.console.agent_connections import AgentConnectionService
from aitest_kit.console.agent_event_log import AgentEventLog
from aitest_kit.console.agent_session_api import _encode_sse
from aitest_kit.console.agent_sessions import AgentSessionManager, _enrich_paths
from aitest_kit.console.app import create_app


def _headers() -> dict[str, str]:
    return {"X-AITest-Console-Token": "console-token"}


def _connection_payload() -> dict[str, object]:
    return {
        "connection_name": "Gateway",
        "protocol": "openai_responses",
        "base_url": "https://gateway.example.test",
        "model": "gpt-5.5",
        "api_key_env": "GATEWAY_API_KEY",
        "api_key": "sk-test-session-value",
    }


class FakeSessionWorker:
    def __init__(self) -> None:
        self.events: queue.Queue[ProtocolMessage] = queue.Queue()
        self.decisions: list[tuple[str, str]] = []
        self.closed = False
        self.start_payload: dict[str, object] = {}

    def start(self, payload) -> ProtocolMessage:
        self.start_payload = dict(payload)
        session_file = payload.get("session_file") or str(Path(payload["session_dir"]) / "pi-fake.jsonl")
        return ProtocolMessage.create("ready", {"session_id": "pi-fake", "session_file": session_file})

    def read_event(self, *, timeout: float | None = None) -> ProtocolMessage:
        try:
            return self.events.get(timeout=timeout)
        except queue.Empty as exc:
            raise AgentWorkerError("WORKER_TIMEOUT", "timeout") from exc

    def send_prompt(self, text: str) -> str:
        message_id = "prompt-1"
        self.events.put(ProtocolMessage.create("session_started", {"session_id": "pi-fake"}, message_id=message_id))
        self.events.put(ProtocolMessage.create("text_delta", {"delta": "正在检查"}, message_id=message_id))
        if text == "invalid permission":
            self.events.put(ProtocolMessage.create(
                "permission_requested",
                {"request_id": "bad", "surface": "write", "target": "suite.md"},
                message_id="bad",
            ))
        else:
            self.events.put(ProtocolMessage.create(
                "tool_call_requested",
                {"tool_call_id": "tool-1", "tool_name": "write", "input": {"path": "suite.md", "content": "new"}},
                message_id=message_id,
            ))
            self.events.put(ProtocolMessage.create(
                "permission_requested",
                {
                    "request_id": "permission-1",
                    "surface": "write",
                    "tool_name": "write",
                    "target": "suite.md",
                },
                message_id="permission-1",
            ))
        return message_id

    def send_permission_decision(self, request_id: str, decision: str) -> str:
        self.decisions.append((request_id, decision))
        message_id = f"decision-{len(self.decisions)}"
        self.events.put(ProtocolMessage.create(
            "permission_resolved",
            {"request_id": request_id, "decision": decision},
            message_id=message_id,
        ))
        if request_id != "bad":
            self.events.put(ProtocolMessage.create(
                "tool_call_finished",
                {"tool_call_id": "tool-1", "tool_name": "write", "is_error": decision == "deny", "result": {}},
                message_id=message_id,
            ))
            self.events.put(ProtocolMessage.create(
                "agent_finished",
                {"status": "succeeded"},
                message_id=message_id,
            ))
        return message_id

    def request_abort(self) -> str:
        self.events.put(ProtocolMessage.create("aborted", {}, message_id="abort-1"))
        self.events.put(ProtocolMessage.create("agent_finished", {"status": "aborted"}, message_id="abort-1"))
        return "abort-1"

    def request_shutdown(self) -> str:
        self.events.put(ProtocolMessage.create("shutdown_complete", {}, message_id="shutdown-1"))
        self.closed = True
        return "shutdown-1"

    def wait_for_exit(self, *, timeout: float | None = None) -> None:
        self.closed = True


def _manager(console_workspace: Path, session_home: Path | None = None) -> tuple[AgentSessionManager, FakeSessionWorker]:
    connection = AgentConnectionService()
    connection.save(console_workspace, _connection_payload())
    worker = FakeSessionWorker()
    return AgentSessionManager(
        connection,
        lambda: console_workspace,
        lambda _env: worker,
        session_home=session_home,
    ), worker


def test_multiple_sessions_survive_manager_restart_and_only_one_is_active(
    console_workspace: Path,
    tmp_path: Path,
) -> None:
    session_home = tmp_path / "agent-sessions"
    manager, first_worker = _manager(console_workspace, session_home)
    first = manager.create("approval", confirmed=False)
    manager.close()

    connection = AgentConnectionService()
    connection.save(console_workspace, _connection_payload())
    resumed_worker = FakeSessionWorker()
    restarted = AgentSessionManager(
        connection,
        lambda: console_workspace,
        lambda _env: resumed_worker,
        session_home=session_home,
    )

    sessions = restarted.list_sessions()
    assert [item["session_id"] for item in sessions] == [first["session_id"]]
    assert restarted.snapshot() is None

    active = restarted.activate(first["session_id"], confirmed=False)
    assert active["is_active"] is True
    assert resumed_worker.start_payload["session_dir"]
    assert restarted.snapshot()["session_id"] == first["session_id"]
    assert first_worker.closed is True
    restarted.close()


def test_two_console_managers_cannot_activate_workers_for_the_same_workspace(
    console_workspace: Path,
    tmp_path: Path,
) -> None:
    session_home = tmp_path / "agent-sessions"
    first, _ = _manager(console_workspace, session_home)
    first.create("approval", confirmed=False)
    second, _ = _manager(console_workspace, session_home)

    try:
        second.create("approval", confirmed=False)
    except Exception as exc:
        assert getattr(exc, "code", None) == "AGENT_WORKER_ALREADY_ACTIVE"
    else:
        raise AssertionError("two Console managers activated Pi Workers for one workspace")

    first.close()
    resumed = second.create("approval", confirmed=False)
    assert resumed["is_active"] is True
    second.close()


def test_running_session_is_interrupted_after_restart(console_workspace: Path, tmp_path: Path) -> None:
    session_home = tmp_path / "agent-sessions"
    manager, _ = _manager(console_workspace, session_home)
    created = manager.create("approval", confirmed=False)
    manager.require(created["session_id"]).send_message("keep running")
    manager.close()

    connection = AgentConnectionService()
    restarted = AgentSessionManager(
        connection,
        lambda: console_workspace,
        lambda _env: FakeSessionWorker(),
        session_home=session_home,
    )
    [restored] = restarted.list_sessions()
    history = restarted.history(restored["session_id"], after_seq=0)

    assert restored["status"] == "interrupted"
    assert restored["active_prompt"] is False
    assert history["events"][-1]["type"] == "session_interrupted"


def test_workspace_switch_is_blocked_while_agent_is_running(console_workspace: Path, tmp_path: Path) -> None:
    manager, _ = _manager(console_workspace, tmp_path / "agent-sessions")
    created = manager.create("approval", confirmed=False)
    manager.require(created["session_id"]).send_message("keep running")

    try:
        manager.ensure_switch_allowed()
    except Exception as exc:
        assert getattr(exc, "code", None) == "AGENT_SESSION_BUSY"
    else:
        raise AssertionError("workspace switch was allowed while the Agent was running")
    finally:
        manager.close()


def test_listing_does_not_interrupt_the_current_running_session(console_workspace: Path, tmp_path: Path) -> None:
    manager, _ = _manager(console_workspace, tmp_path / "agent-sessions")
    created = manager.create("approval", confirmed=False)
    session = manager.require(created["session_id"])
    session.send_message("keep running")

    [listed] = manager.list_sessions()
    activated = manager.activate(created["session_id"], confirmed=False)

    assert listed["status"] in {"running", "awaiting_approval"}
    assert listed["is_active"] is True
    assert activated["status"] in {"running", "awaiting_approval"}
    assert all(event["type"] != "session_interrupted" for event in session.events.replay(0).events)
    manager.close()


def test_session_title_does_not_persist_credential_shaped_prompt_text(console_workspace: Path, tmp_path: Path) -> None:
    manager, _ = _manager(console_workspace, tmp_path / "agent-sessions")
    created = manager.create("approval", confirmed=False)
    manager.require(created["session_id"]).send_message("use sk-examplecredential123456789 for this check")

    [listed] = manager.list_sessions()

    assert "sk-examplecredential123456789" not in listed["title"]
    manager.close()


def _wait_until(predicate, timeout: float = 2) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition was not reached")


def test_full_trust_requires_explicit_confirmation(console_workspace: Path) -> None:
    manager, _ = _manager(console_workspace)

    try:
        manager.create("full_trust", confirmed=False)
    except Exception as exc:
        assert getattr(exc, "code", None) == "FULL_TRUST_CONFIRMATION_REQUIRED"
    else:
        raise AssertionError("full trust was created without confirmation")


def test_full_trust_requires_confirmation_again_when_activated(console_workspace: Path, tmp_path: Path) -> None:
    session_home = tmp_path / "agent-sessions"
    manager, _ = _manager(console_workspace, session_home)
    created = manager.create("full_trust", confirmed=True)
    manager.close()

    restarted, _ = _manager(console_workspace, session_home)
    try:
        restarted.activate(created["session_id"], confirmed=False)
    except Exception as exc:
        assert getattr(exc, "code", None) == "FULL_TRUST_CONFIRMATION_REQUIRED"
    else:
        raise AssertionError("full trust was resumed without confirmation")

    resumed = restarted.activate(created["session_id"], confirmed=True)
    assert resumed["is_active"] is True
    restarted.close()


def test_session_creation_surfaces_missing_runtime_as_structured_error(console_workspace: Path) -> None:
    connection = AgentConnectionService()
    connection.save(console_workspace, _connection_payload())

    def missing_runtime(_environment):
        raise AgentWorkerError("AGENT_RUNTIME_NOT_INSTALLED", "run aitest agent setup")

    manager = AgentSessionManager(connection, lambda: console_workspace, missing_runtime)

    try:
        manager.create("approval", confirmed=False)
    except Exception as exc:
        assert getattr(exc, "code", None) == "AGENT_RUNTIME_NOT_INSTALLED"
    else:
        raise AssertionError("missing Runtime must block session creation")


def test_session_projects_prompt_approval_and_terminal_events(console_workspace: Path) -> None:
    manager, worker = _manager(console_workspace)
    snapshot = manager.create("approval", confirmed=False)
    session = manager.require(snapshot["session_id"])

    session.send_message("write the suite")
    _wait_until(lambda: bool(session.pending_approvals))
    assert session.status == "awaiting_approval"
    session.resolve_approval("permission-1", "allow_once")
    _wait_until(lambda: session.status == "succeeded")

    replay = session.events.replay(0)
    types = [event["type"] for event in replay.events]
    tool = next(event for event in replay.events if event["type"] == "tool_call_requested")
    assert types[:2] == ["session_created", "user_message"]
    assert "permission_requested" in types
    assert types[-1] == "agent_finished"
    assert tool["payload"]["input"]["workspace_path"] == "suite.md"
    assert worker.decisions == [("permission-1", "allow_once")]
    manager.close()


def test_invalid_permission_request_is_denied_before_projection(console_workspace: Path) -> None:
    manager, worker = _manager(console_workspace)
    snapshot = manager.create("approval", confirmed=False)
    session = manager.require(snapshot["session_id"])

    session.send_message("invalid permission")
    _wait_until(lambda: bool(worker.decisions))

    types = [event["type"] for event in session.events.replay(0).events]
    assert worker.decisions == [("bad", "deny")]
    assert "permission_invalid" in types
    assert "permission_requested" not in types
    manager.close()


def test_deny_and_abort_reach_terminal_states(console_workspace: Path) -> None:
    manager, worker = _manager(console_workspace)
    snapshot = manager.create("approval", confirmed=False)
    session = manager.require(snapshot["session_id"])

    session.send_message("write the suite")
    _wait_until(lambda: bool(session.pending_approvals))
    session.resolve_approval("permission-1", "deny")
    _wait_until(lambda: session.status == "succeeded")
    assert worker.decisions == [("permission-1", "deny")]

    session.send_message("write the suite")
    _wait_until(lambda: session.active_prompt)
    session.abort()
    _wait_until(lambda: session.status == "aborted")
    assert session.active_prompt is False
    terminal_events = [event for event in session.events.replay(0).events if event["type"] == "agent_finished"]
    assert [event["payload"]["status"] for event in terminal_events] == ["succeeded", "aborted"]
    manager.close()


def test_event_log_trims_and_requires_resync_for_stale_cursor() -> None:
    log = AgentEventLog()
    for index in range(1005):
        log.append("session", "text_delta", {"delta": str(index)})

    replay = log.replay(0)

    assert replay.resync_required is True
    assert replay.events[0]["seq"] == 6
    assert replay.events[-1]["seq"] == 1005


def test_sse_encoder_emits_standard_id_event_and_json_data() -> None:
    event = AgentEventLog().append("session", "text_delta", {"delta": "你好"})

    encoded = _encode_sse(event)

    assert encoded.startswith("id: 1\nevent: text_delta\ndata: ")
    assert '"delta":"你好"' in encoded
    assert encoded.endswith("\n\n")


def test_tool_path_link_is_added_only_for_workspace_paths(console_workspace: Path, tmp_path: Path) -> None:
    inside = _enrich_paths(
        console_workspace,
        "tool_call_requested",
        {"input": {"path": "test_workspace/suites/demo/orders_smoke/business.md"}},
    )
    outside = _enrich_paths(
        console_workspace,
        "tool_call_requested",
        {"input": {"path": str(tmp_path / "external.md")}},
    )

    assert inside["input"]["workspace_path"] == "test_workspace/suites/demo/orders_smoke/business.md"
    assert "workspace_path" not in outside["input"]


def test_agent_session_api_is_authenticated_and_no_store(console_workspace: Path, tmp_path: Path) -> None:
    worker = FakeSessionWorker()
    app = create_app(
        initial_workspace=console_workspace,
        token="console-token",
        agent_worker_factory=lambda _env: worker,
        agent_session_home=tmp_path / "agent-sessions",
    )
    app.state.console_runtime.agent_connections.save(console_workspace, _connection_payload())

    with TestClient(app) as client:
        unauthorized = client.get("/api/agent/session")
        created = client.post(
            "/api/agent/sessions",
            headers=_headers(),
            json={"permission_mode": "approval", "confirmed": False},
        )
        second = client.post(
            "/api/agent/sessions",
            headers=_headers(),
            json={"permission_mode": "approval", "confirmed": False},
        )
        listed = client.get("/api/agent/sessions", headers=_headers())
        history = client.get(
            f"/api/agent/sessions/{created.json()['session_id']}/history",
            headers=_headers(),
        )
        activated = client.post(
            f"/api/agent/sessions/{created.json()['session_id']}/activate",
            headers=_headers(),
            json={"confirmed": False},
        )
        fetched = client.get("/api/agent/session", headers=_headers())
        archived = client.post(
            f"/api/agent/sessions/{second.json()['session_id']}/archive",
            headers=_headers(),
        )
        deleted = client.delete(f"/api/agent/sessions/{created.json()['session_id']}", headers=_headers())

    assert unauthorized.status_code == 401
    assert created.status_code == 200
    assert second.status_code == 200
    assert len(listed.json()["sessions"]) == 2
    assert history.json()["events"][0]["type"] == "session_created"
    assert activated.json()["session_id"] == created.json()["session_id"]
    assert fetched.json()["session_id"] == created.json()["session_id"]
    assert fetched.headers["cache-control"] == "no-store"
    assert archived.status_code == 204
    assert deleted.status_code == 204
    assert worker.closed is True
