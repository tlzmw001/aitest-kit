"""The test workbench runs independently of an embedded Agent runtime."""
from click.testing import CliRunner
from fastapi.testclient import TestClient

from aitest_kit.cli import main
from aitest_kit.console.app import create_app


def test_cli_retains_testing_commands_without_embedded_agent():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "agent" not in main.commands
    assert {"console", "codegen", "run", "report", "doctor", "upgrade"} <= set(main.commands)
    result = runner.invoke(main, ["agent", "setup"])
    assert result.exit_code == 2
    assert "No such command 'agent'" in result.output


def test_console_has_no_agent_api_and_preserves_legacy_data(console_workspace, tmp_path, monkeypatch):
    legacy = tmp_path / "legacy-agent"
    legacy.mkdir()
    journal = legacy / "events.jsonl"
    journal.write_text('{"legacy":true}\n', encoding="utf-8")
    monkeypatch.setenv("AITEST_AGENT_SESSION_HOME", str(legacy))
    monkeypatch.setenv("AITEST_RUNTIME_HOME", str(tmp_path / "runtime-must-not-be-created"))
    config = console_workspace / "aitest_config" / "aitest.yaml"
    original_config = config.read_bytes()
    app = create_app(initial_workspace=console_workspace, token="test-token")
    with TestClient(app) as client:
        headers = {"X-AITest-Console-Token": "test-token"}
        assert client.get("/api/health", headers=headers).json() == {"status": "ok"}
        assert client.get("/api/workspace").status_code == 401
        assert client.get("/api/workspace", headers=headers).status_code == 200
        for path in ("/api/agent/session", "/api/agent/connection", "/api/agent/runtime", "/api/agent/sessions"):
            assert client.get(path, headers=headers).status_code == 404
        response = client.get("/api/files", params={"path": "aitest_config/aitest.yaml"}, headers=headers)
        assert response.status_code == 200
    assert config.read_bytes() == original_config
    assert journal.read_text(encoding="utf-8") == '{"legacy":true}\n'
    assert list(legacy.iterdir()) == [journal]
    assert not (tmp_path / "runtime-must-not-be-created").exists()
