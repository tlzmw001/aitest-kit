from __future__ import annotations

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

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

    with (
        patch("uvicorn.run") as run,
        patch(
            "aitest_kit.console.cli.secrets.token_urlsafe",
            side_effect=["secret-token", "launch-id"],
        ),
    ):
        result = CliRunner().invoke(
            console_command,
            ["--workspace", str(console_workspace), "--port", "8123", "--no-open"],
        )

    assert result.exit_code == 0, result.output
    session_url = next(
        line.removeprefix("Session URL: ")
        for line in result.output.splitlines()
        if line.startswith("Session URL: ")
    )
    parsed_session_url = urlparse(session_url)
    session_query = parse_qs(parsed_session_url.query)
    assert session_query == {"launch": ["launch-id"]}
    assert parsed_session_url.fragment == "token=secret-token"
    assert "token" not in session_query
    app = run.call_args.args[0]
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert '<div id="app"></div>' in response.text
    run.assert_called_once()


def test_console_auto_open_forces_a_new_document_navigation(console_workspace):
    class ImmediateTimer:
        def __init__(self, _delay, callback):
            self.callback = callback

        def start(self):
            self.callback()

    with (
        patch("uvicorn.run") as run,
        patch("aitest_kit.console.cli.webbrowser.open") as open_browser,
        patch("aitest_kit.console.cli.threading.Timer", ImmediateTimer),
        patch(
            "aitest_kit.console.cli.secrets.token_urlsafe",
            side_effect=["secret-token", "launch-id"],
        ),
    ):
        result = CliRunner().invoke(
            console_command,
            ["--workspace", str(console_workspace), "--port", "8123"],
        )

    assert result.exit_code == 0, result.output
    open_browser.assert_called_once_with(
        "http://127.0.0.1:8123/?launch=launch-id#token=secret-token"
    )
    run.assert_called_once()


def test_console_can_start_without_an_initial_workspace():
    with patch("uvicorn.run") as run:
        result = CliRunner().invoke(console_command, ["--port", "8123", "--no-open"])

    assert result.exit_code == 0, result.output
    app = run.call_args.args[0]
    response = TestClient(app).get("/api/workspace", headers={"X-AITest-Console-Token": "invalid"})
    assert response.status_code == 401
    run.assert_called_once()
