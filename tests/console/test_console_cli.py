from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner
from fastapi.testclient import TestClient

from aitest_kit.console.cli import console_command


def test_console_requires_explicit_port(console_workspace):
    result = CliRunner().invoke(console_command, ["--workspace", str(console_workspace), "--no-open"])

    assert result.exit_code == 2
    assert "--port" in result.output


def test_console_rejects_non_loopback_host(console_workspace):
    result = CliRunner().invoke(
        console_command,
        ["--workspace", str(console_workspace), "--host", "0.0.0.0", "--port", "8123", "--no-open"],
    )

    assert result.exit_code == 1
    assert "only allows loopback" in result.output


def test_console_serves_packaged_frontend_independent_of_workspace(console_workspace):
    assert not (console_workspace / "console_web").exists()

    with patch("uvicorn.run") as run:
        result = CliRunner().invoke(
            console_command,
            ["--workspace", str(console_workspace), "--port", "8123", "--no-open"],
        )

    assert result.exit_code == 0, result.output
    assert "#token=" in result.output
    assert "/?token=" not in result.output
    app = run.call_args.args[0]
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert '<div id="app"></div>' in response.text
    run.assert_called_once()


def test_console_can_start_without_an_initial_workspace():
    with patch("uvicorn.run") as run:
        result = CliRunner().invoke(console_command, ["--port", "8123", "--no-open"])

    assert result.exit_code == 0, result.output
    app = run.call_args.args[0]
    response = TestClient(app).get("/api/workspace", headers={"X-AITest-Console-Token": "invalid"})
    assert response.status_code == 401
    run.assert_called_once()
