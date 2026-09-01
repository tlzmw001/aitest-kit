from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from aitest_kit.agent.client import AgentWorkerError
from aitest_kit.console.agent_connections import (
    AgentConnectionAttempt,
    AgentConnectionAttemptError,
    AgentConnectionService,
    test_pi_connection as run_pi_connection_test,
)
from aitest_kit.console.app import create_app


def _headers() -> dict[str, str]:
    return {"X-AITest-Console-Token": "console-token"}


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "connection_name": "Gateway",
        "protocol": "openai_responses",
        "base_url": "https://gateway.example.test",
        "model": "gpt-5.5",
        "api_key_env": "GATEWAY_API_KEY",
        "api_key": "sk-test-secret-value",
    }
    payload.update(overrides)
    return payload


def test_save_connection_persists_only_nonsecret_config(console_workspace: Path) -> None:
    config_path = console_workspace / "aitest_config" / "aitest.yaml"
    original = config_path.read_text(encoding="utf-8")
    config_path.write_text(original.replace("workspace:", "# workspace settings must survive\nworkspace:"), encoding="utf-8")
    client = TestClient(create_app(initial_workspace=console_workspace, token="console-token"))

    response = client.put("/api/agent/connection", headers=_headers(), json=_payload())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["has_api_key"] is True
    assert body["credential_source"] == "session"
    assert "api_key" not in body
    config_text = config_path.read_text(encoding="utf-8")
    assert "sk-test-secret-value" not in config_text
    assert "connection_name: Gateway" in config_text
    assert "protocol: openai_responses" in config_text
    assert "provider: openai" in config_text
    assert "base_url: https://gateway.example.test" in config_text
    assert "# workspace settings must survive" in config_text
    assert "workspace:" in config_text


def test_connection_get_never_returns_session_key(console_workspace: Path) -> None:
    client = TestClient(create_app(initial_workspace=console_workspace, token="console-token"))
    client.put("/api/agent/connection", headers=_headers(), json=_payload())

    response = client.get("/api/agent/connection", headers=_headers())

    rendered = response.text
    assert response.status_code == 200
    assert response.json()["has_api_key"] is True
    assert response.json()["credential_source"] == "session"
    assert response.headers["cache-control"] == "no-store"
    assert "sk-test-secret-value" not in rendered
    assert '"api_key":' not in rendered


def test_connection_test_surfaces_missing_runtime_as_structured_error(console_workspace: Path, monkeypatch) -> None:
    def missing_runtime():
        raise AgentWorkerError("AGENT_RUNTIME_NOT_INSTALLED", "run aitest agent setup")

    monkeypatch.setattr("aitest_kit.console.agent_connections.default_worker_command", missing_runtime)
    client = TestClient(create_app(initial_workspace=console_workspace, token="console-token"))

    response = client.post("/api/agent/connection/test", headers=_headers(), json=_payload())

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AGENT_RUNTIME_NOT_INSTALLED"


def test_connection_get_never_resolves_base_url_environment(
    console_workspace: Path,
    monkeypatch,
) -> None:
    config_path = console_workspace / "aitest_config" / "aitest.yaml"
    config_text = config_path.read_text(encoding="utf-8")
    config_path.write_text(
        config_text.replace("base_url_env: null", "base_url_env: PRIVATE_GATEWAY_URL"),
        encoding="utf-8",
    )
    monkeypatch.setenv("PRIVATE_GATEWAY_URL", "private-value-that-must-not-reach-the-browser")
    client = TestClient(create_app(initial_workspace=console_workspace, token="console-token"))

    response = client.get("/api/agent/connection", headers=_headers())

    assert response.status_code == 200
    assert response.json()["base_url"] == ""
    assert "private-value-that-must-not-reach-the-browser" not in response.text


def test_connection_rejects_oversized_key_without_echoing_it(console_workspace: Path) -> None:
    client = TestClient(create_app(initial_workspace=console_workspace, token="console-token"))
    oversized_key = "s" * 4097

    response = client.put(
        "/api/agent/connection",
        headers=_headers(),
        json=_payload(api_key=oversized_key),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AGENT_API_KEY_INVALID"
    assert oversized_key not in response.text


def test_connection_rejects_unsafe_base_url(console_workspace: Path) -> None:
    client = TestClient(create_app(initial_workspace=console_workspace, token="console-token"))

    response = client.put(
        "/api/agent/connection",
        headers=_headers(),
        json=_payload(base_url="file:///tmp/credential"),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AGENT_BASE_URL_INVALID"


def test_test_connection_uses_real_tester_contract_without_returning_key(console_workspace: Path) -> None:
    captured: dict[str, str] = {}

    def fake_tester(attempt):
        captured["protocol"] = attempt.protocol
        captured["api_key"] = attempt.api_key
        return "OK"

    client = TestClient(
        create_app(
            initial_workspace=console_workspace,
            token="console-token",
            agent_connection_tester=fake_tester,
        )
    )

    response = client.post("/api/agent/connection/test", headers=_headers(), json=_payload())

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "connected"
    assert response.json()["detected_protocol"] == "openai_responses"
    assert response.json()["internal_provider"] == "openai"
    assert response.json()["response_text"] == "OK"
    assert captured == {"protocol": "openai_responses", "api_key": "sk-test-secret-value"}
    assert "sk-test-secret-value" not in response.text


def test_auto_detection_falls_back_only_for_protocol_mismatch(console_workspace: Path) -> None:
    attempts: list[str] = []

    def fake_tester(attempt):
        attempts.append(attempt.protocol)
        if attempt.protocol == "openai_responses":
            raise AgentConnectionAttemptError("protocol_mismatch", "endpoint returned 404")
        return "OK"

    client = TestClient(
        create_app(
            initial_workspace=console_workspace,
            token="console-token",
            agent_connection_tester=fake_tester,
        )
    )

    response = client.post(
        "/api/agent/connection/test",
        headers=_headers(),
        json=_payload(protocol="auto"),
    )

    assert response.status_code == 200, response.text
    assert response.json()["detected_protocol"] == "openai_chat_completions"
    assert response.json()["internal_provider"] == "aitest-openai-chat"
    assert attempts == ["openai_responses", "openai_chat_completions"]


def test_auto_detection_does_not_fallback_after_auth_failure(console_workspace: Path) -> None:
    attempts: list[str] = []

    def fake_tester(attempt):
        attempts.append(attempt.protocol)
        raise AgentConnectionAttemptError("authentication", "invalid key sk-test-secret-value")

    client = TestClient(
        create_app(
            initial_workspace=console_workspace,
            token="console-token",
            agent_connection_tester=fake_tester,
        )
    )

    response = client.post(
        "/api/agent/connection/test",
        headers=_headers(),
        json=_payload(protocol="auto"),
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AGENT_AUTHENTICATION_FAILED"
    assert attempts == ["openai_responses"]
    assert "sk-test-secret-value" not in response.text


def test_workspace_switch_clears_session_key(console_workspace: Path, tmp_path: Path) -> None:
    service = AgentConnectionService()
    service.save(console_workspace, _payload())
    assert service.get(console_workspace)["has_api_key"] is True

    service.clear_session_keys()

    assert service.get(console_workspace)["has_api_key"] is False


def test_runtime_launch_uses_session_key_without_exposing_it_in_payload(console_workspace: Path) -> None:
    service = AgentConnectionService()
    service.save(console_workspace, _payload())
    (console_workspace / ".codex" / "skills").mkdir(parents=True)

    launch = service.runtime_launch(console_workspace, permission_mode="approval")

    assert launch.environment["GATEWAY_API_KEY"] == "sk-test-secret-value"
    assert launch.initialize_payload["permission_mode"] == "approval"
    assert launch.initialize_payload["tools"] == ["read", "write", "edit", "grep", "find", "ls", "bash"]
    assert launch.initialize_payload["skill_paths"] == [str(console_workspace / ".codex" / "skills")]
    assert "sk-test-secret-value" not in str(launch.initialize_payload)


def test_runtime_launch_requires_available_key(console_workspace: Path) -> None:
    service = AgentConnectionService()
    service.save(console_workspace, _payload(api_key=None))

    try:
        service.runtime_launch(console_workspace, permission_mode="approval")
    except Exception as exc:
        assert getattr(exc, "code", None) == "AGENT_API_KEY_REQUIRED"
    else:
        raise AssertionError("runtime launch accepted a missing API key")


def test_real_connection_helper_disables_all_agent_tools(console_workspace: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeWorkerClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def start(self, payload):
            captured.update(payload)

        def run_prompt(self, *_args, **_kwargs):
            return [type("Event", (), {"type": "text_delta", "payload": {"delta": "OK"}})()]

    monkeypatch.setattr("aitest_kit.console.agent_connections.WorkerClient", FakeWorkerClient)
    monkeypatch.setattr("aitest_kit.console.agent_connections.default_worker_command", lambda: ["node"])

    response = run_pi_connection_test(
        AgentConnectionAttempt(
            workspace=console_workspace,
            protocol="openai_responses",
            provider="openai",
            base_url="https://gateway.example.test",
            model="gpt-5.5",
            api_key="session-secret",
        )
    )

    assert response == "OK"
    assert captured["skill_paths"] == []
    assert captured["tools"] == []
    assert captured["permission_mode"] == "approval"
