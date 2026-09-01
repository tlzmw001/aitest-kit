from __future__ import annotations

import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from aitest_kit.console.agent_runtime import AgentRuntimeService
from aitest_kit.console.app import create_app


def _headers() -> dict[str, str]:
    return {"X-AITest-Console-Token": "console-token"}


def _ready_status() -> dict[str, object]:
    return {
        "state": "ready",
        "source": "user",
        "message": "ready",
        "runtime_dir": "/tmp/pi-runtime",
        "bundle_hash": "a" * 64,
        "minimum_node_version": "22.19.0",
        "node_version": "v24.14.0",
        "npm_version": "11.9.0",
        "registry": "https://registry.npmjs.org/",
        "dependencies": [],
        "setup_command": "aitest agent setup",
    }


def test_runtime_status_requires_token_and_disables_cache_without_workspace(monkeypatch) -> None:
    monkeypatch.setattr("aitest_kit.console.agent_runtime.runtime_status", _ready_status)
    client = TestClient(create_app(token="console-token"))

    unauthorized = client.get("/api/agent/runtime")
    response = client.get("/api/agent/runtime", headers=_headers())

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.json()["source"] == "user"
    assert response.headers["cache-control"] == "no-store"


def test_runtime_setup_requires_explicit_confirmation(console_workspace: Path, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AITEST_RUNTIME_HOME", str(tmp_path / "runtime-home"))
    client = TestClient(create_app(initial_workspace=console_workspace, token="console-token"))

    response = client.post("/api/agent/runtime/setup", headers=_headers(), json={"confirmed": False})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AGENT_RUNTIME_SETUP_CONFIRMATION_REQUIRED"
    assert not (tmp_path / "runtime-home").exists()


def test_runtime_setup_job_can_be_queried_without_workspace_mutation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime-home"
    monkeypatch.setenv("AITEST_RUNTIME_HOME", str(runtime_root))
    monkeypatch.setattr(
        "aitest_kit.console.agent_runtime.runtime_setup_command",
        lambda: [sys.executable, "-c", "print('runtime installed')"],
    )
    client = TestClient(create_app(token="console-token"))

    started = client.post("/api/agent/runtime/setup", headers=_headers(), json={"confirmed": True})
    job_id = started.json()["id"]
    deadline = time.monotonic() + 5
    body = started.json()
    while body["status"] in {"queued", "running"} and time.monotonic() < deadline:
        body = client.get(f"/api/agent/runtime/setup/{job_id}", headers=_headers()).json()

    assert started.status_code == 200
    assert body["status"] == "succeeded"
    assert "runtime installed" in body["output"]
    assert body["command_summary"] == "aitest agent setup"
    assert runtime_root.is_dir()


def test_runtime_setup_rejects_active_agent_session(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AITEST_RUNTIME_HOME", str(tmp_path / "runtime-home"))
    service = AgentRuntimeService(lambda: {"id": "active"})

    try:
        service.start_setup(confirmed=True)
    except Exception as exc:
        assert getattr(exc, "code", "") == "AGENT_SESSION_ACTIVE"
    else:
        raise AssertionError("active session must block Runtime setup")


def test_unknown_runtime_setup_job_uses_stable_error(console_workspace: Path, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AITEST_RUNTIME_HOME", str(tmp_path / "runtime-home"))
    client = TestClient(create_app(initial_workspace=console_workspace, token="console-token"))

    response = client.get("/api/agent/runtime/setup/missing", headers=_headers())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AGENT_RUNTIME_SETUP_JOB_NOT_FOUND"


def test_runtime_setup_job_can_be_cancelled(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AITEST_RUNTIME_HOME", str(tmp_path / "runtime-home"))
    monkeypatch.setattr(
        "aitest_kit.console.agent_runtime.runtime_setup_command",
        lambda: [sys.executable, "-c", "import time; print('started', flush=True); time.sleep(30)"],
    )
    client = TestClient(create_app(token="console-token"))
    started = client.post("/api/agent/runtime/setup", headers=_headers(), json={"confirmed": True}).json()
    job_id = started["id"]
    deadline = time.monotonic() + 5
    body = started
    while "started" not in body["output"] and time.monotonic() < deadline:
        body = client.get(f"/api/agent/runtime/setup/{job_id}", headers=_headers()).json()

    cancelled = client.post(f"/api/agent/runtime/setup/{job_id}/cancel", headers=_headers()).json()
    while cancelled["status"] in {"queued", "running"} and time.monotonic() < deadline:
        cancelled = client.get(f"/api/agent/runtime/setup/{job_id}", headers=_headers()).json()

    assert cancelled["status"] == "cancelled"
    assert cancelled["cancel_requested"] is True
