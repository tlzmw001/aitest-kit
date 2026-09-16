from __future__ import annotations

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from aitest_kit.agent.client import WorkerClient
from aitest_kit.console.agent_diagnostics import DiagnosticProjection
from aitest_kit.console.agent_session_api import AgentMessageRequest
from aitest_kit.agent.protocol import ProtocolMessage
from aitest_kit.console.app import create_app
from tests.console.test_console_agent_sessions import _manager, FakeSessionWorker, _connection_payload, _headers


def test_message_diagnostics_is_optional_and_enum_checked():
    assert AgentMessageRequest(text="hello").diagnostics == "basic"
    assert AgentMessageRequest(text="hello", diagnostics="stream").diagnostics == "stream"
    with pytest.raises(ValidationError):
        AgentMessageRequest(text="hello", diagnostics="raw-secrets")


def test_worker_client_keeps_default_wire_payload_and_forwards_opt_in(monkeypatch):
    calls = []
    monkeypatch.setattr(WorkerClient, "send", lambda _, kind, payload: calls.append((kind, payload)) or "m")
    client = WorkerClient(["unused"])
    client.send_prompt("hello")
    client.send_prompt("hello", diagnostics="stream")
    assert calls == [("prompt", {"text": "hello"}), ("prompt", {"text": "hello", "diagnostics": "stream"})]


def test_projection_bounds_requests_and_does_not_expose_mutable_state():
    projection = DiagnosticProjection()
    for index in range(30):
        projection.apply("request_diagnostic", {"request_id": str(index), "message_id": "m", "phase": "completed"})
    snapshot = projection.snapshot()
    assert len(snapshot["requests"]) == 20
    snapshot["requests"].clear()
    assert len(projection.snapshot()["requests"]) == 20
    projection.apply("agent_retry", {"message_id": "m", "phase": "start", "attempt": 1})
    projection.apply("user_message", {})
    assert projection.snapshot()["retry"] is None


def test_live_snapshot_retains_diagnostics_after_event_window_rollover(console_workspace, tmp_path, monkeypatch):
    manager, worker = _manager(console_workspace, tmp_path / "sessions")
    try:
        info = manager.create("approval", confirmed=False)
        session = manager.require(info["session_id"])
        payload = {"request_id": "r", "message_id": "m", "phase": "waiting_text", "http_status": 200}
        session._handle_worker_event(ProtocolMessage.create("request_diagnostic", payload, message_id="m"))
        # Force retention pressure without 1000 disk fsyncs. Snapshot must not depend on retained events.
        monkeypatch.setattr("aitest_kit.console.agent_event_log.MAX_EVENT_COUNT", 2)
        for _ in range(4):
            session._handle_worker_event(ProtocolMessage.create("text_delta", {"delta": "x"}, message_id="m"))
        replay = session.event_replay(0)
        assert all(e["type"] != "request_diagnostic" for e in replay["events"])
        assert replay["session"]["diagnostics"]["requests"] == [payload]
    finally:
        manager.close()


def test_diagnostics_journal_history_survives_close(console_workspace, tmp_path):
    manager, _ = _manager(console_workspace, tmp_path / "sessions")
    info = manager.create("approval", confirmed=False)
    payload = {"request_id": "r", "message_id": "m", "phase": "completed", "complete_ms": 123}
    manager.require(info["session_id"])._handle_worker_event(ProtocolMessage.create("request_diagnostic", payload))
    manager.close()
    history = manager.history(info["session_id"], after_seq=0)
    assert history["session"]["diagnostics"]["requests"] == [payload]


def test_authenticated_http_forwards_one_shot_mode_to_worker(console_workspace, tmp_path):
    class RecordingWorker(FakeSessionWorker):
        modes = []

        def send_prompt(self, text, *, diagnostics="basic"):
            self.modes.append(diagnostics)
            return "m"

    worker = RecordingWorker()
    app = create_app(initial_workspace=console_workspace, token="console-token",
                     agent_worker_factory=lambda _: worker, agent_session_home=tmp_path / "sessions")
    app.state.console_runtime.agent_connections.save(console_workspace, _connection_payload())
    with TestClient(app) as client:
        session = client.post("/api/agent/sessions", headers=_headers(), json={"permission_mode": "approval"}).json()
        url = f"/api/agent/sessions/{session['session_id']}/messages"
        assert client.post(url, json={"text": "hello", "diagnostics": "stream"}).status_code == 401
        assert client.post(url, headers=_headers(), json={"text": "hello", "diagnostics": "invalid"}).status_code == 422
        assert worker.modes == []
        response = client.post(url, headers=_headers(), json={"text": "hello", "diagnostics": "stream"})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert worker.modes == ["stream"]
        active = app.state.console_runtime.agent_sessions.require(session["session_id"])
        active._handle_worker_event(ProtocolMessage.create("agent_finished", {"status": "succeeded"}))
        assert client.post(url, headers=_headers(), json={"text": "next"}).status_code == 200
        assert worker.modes == ["stream", "basic"]
