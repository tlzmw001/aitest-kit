from __future__ import annotations

import sys
from pathlib import Path

import pytest

from aitest_kit.agent.client import AgentWorkerError, WorkerClient


FAKE_WORKER = Path(__file__).with_name("fake_worker.py")


def make_client() -> WorkerClient:
    return WorkerClient(
        [sys.executable, str(FAKE_WORKER)],
        startup_timeout=2,
        message_timeout=2,
        shutdown_timeout=2,
    )


def test_client_handshake_permission_and_event_flow() -> None:
    client = make_client()
    seen: list[str] = []
    approvals: list[str] = []

    try:
        ready = client.start({"cwd": "/tmp/workspace"})
        events = client.run_prompt(
            "write the suite",
            on_event=lambda event: seen.append(event.type),
            approval_handler=lambda event: approvals.append(event.payload["request_id"]) or "allow_once",
        )
    finally:
        client.close()

    assert ready.type == "ready"
    assert approvals == ["permission-1"]
    assert "tool_call_requested" in seen
    assert "permission_requested" in seen
    assert "permission_resolved" in seen
    assert events[-1].type == "agent_finished"
    assert client.returncode == 0


def test_client_fails_closed_without_approval_handler() -> None:
    client = make_client()
    try:
        client.start({"cwd": "/tmp/workspace"})
        events = client.run_prompt("write the suite")
    finally:
        client.close()

    resolved = next(event for event in events if event.type == "permission_resolved")
    assert resolved.payload["decision"] == "deny"


def test_client_surfaces_worker_error() -> None:
    client = make_client()
    try:
        client.start({"cwd": "/tmp/workspace"})
        with pytest.raises(AgentWorkerError) as exc_info:
            client.run_prompt("error")
    finally:
        client.close()

    assert exc_info.value.code == "FAKE_ERROR"


def test_client_abort_and_cleanup() -> None:
    client = make_client()
    client.start({"cwd": "/tmp/workspace"})
    client.send("prompt", {"text": "hang"})

    aborted = client.abort()
    client.close()

    assert aborted.type == "aborted"
    assert client.returncode == 0


def test_client_reports_worker_crash() -> None:
    client = make_client()
    try:
        client.start({"cwd": "/tmp/workspace"})
        with pytest.raises(AgentWorkerError) as exc_info:
            client.run_prompt("crash")
    finally:
        client.close()

    assert exc_info.value.code == "WORKER_EXITED"
    assert "23" in str(exc_info.value)


def test_client_timeout_still_cleans_up_worker() -> None:
    client = make_client()
    try:
        client.start({"cwd": "/tmp/workspace"})
        with pytest.raises(AgentWorkerError) as exc_info:
            client.run_prompt("hang", timeout=0.05)
    finally:
        client.close()

    assert exc_info.value.code == "WORKER_TIMEOUT"
    assert client.returncode == 0


def test_client_redacts_arbitrary_key_values_from_worker_stderr() -> None:
    client = WorkerClient(
        [sys.executable, "-c", "import sys; sys.stderr.write('arbitrary-provider-credential\\n'); raise SystemExit(7)"],
        env={"PATH": "/usr/bin", "MODEL_API_KEY": "arbitrary-provider-credential"},
        startup_timeout=1,
        shutdown_timeout=1,
    )
    try:
        with pytest.raises(AgentWorkerError) as exc_info:
            client.start({"cwd": "/tmp/workspace"})
    finally:
        client.close()

    assert "arbitrary-provider-credential" not in str(exc_info.value.details)
    assert "[REDACTED]" in str(exc_info.value.details)
