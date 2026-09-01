from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from aitest_kit.agent.cli import agent_command
from aitest_kit.agent.config import AgentConfig, AgentModelConfig
from aitest_kit.agent.doctor import DoctorCheck, format_doctor_checks


def test_doctor_formatter_never_prints_secret_values() -> None:
    checks = [
        DoctorCheck("api_key_env", True, "ANTHROPIC_API_KEY is set"),
        DoctorCheck("worker", False, "worker failed", details={"authorization": "Bearer secret"}),
    ]

    rendered = format_doctor_checks(checks)

    assert "ANTHROPIC_API_KEY" in rendered
    assert "Bearer secret" not in rendered


def test_agent_doctor_cli_reports_checks_without_revealing_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "aitest_kit.agent.cli.run_agent_doctor",
        lambda workspace: [DoctorCheck("node", True, "Node v24.14.0"), DoctorCheck("api_key_env", True, "ANTHROPIC_API_KEY is set")],
    )

    result = CliRunner().invoke(agent_command, ["doctor", "--workspace", str(tmp_path)])

    assert result.exit_code == 0
    assert "Node v24.14.0" in result.output
    assert "ANTHROPIC_API_KEY is set" in result.output


def test_agent_setup_uses_shared_runtime_installer_without_workspace(monkeypatch) -> None:
    calls = []

    def fake_install(*, progress):
        progress("Installing locked dependencies...")
        calls.append("install")
        return {"installed": True, "runtime_dir": "/tmp/runtime", "bundle_hash": "a" * 64}

    monkeypatch.setattr("aitest_kit.agent.cli.install_runtime", fake_install)

    result = CliRunner().invoke(agent_command, ["setup"])

    assert result.exit_code == 0
    assert calls == ["install"]
    assert "Installing locked dependencies" in result.output
    assert "/tmp/runtime" in result.output


def test_full_trust_requires_explicit_confirmation_before_loading_config(monkeypatch, tmp_path: Path) -> None:
    loaded = []
    monkeypatch.setattr("aitest_kit.agent.cli.load_agent_config", lambda _workspace: loaded.append(True))

    result = CliRunner().invoke(
        agent_command,
        ["run", "--workspace", str(tmp_path), "--mode", "full_trust", "--prompt", "hello"],
        input="n\n",
    )

    assert result.exit_code != 0
    assert "继承当前本机用户权限" in result.output
    assert loaded == []


def test_agent_run_starts_worker_with_referenced_model(monkeypatch, tmp_path: Path) -> None:
    calls = []

    class FakeWorkerClient:
        def __init__(self, command, env):
            calls.append(("construct", command, env))

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            calls.append(("close",))

        def start(self, payload):
            calls.append(("start", payload))

        def run_prompt(self, text, **_kwargs):
            calls.append(("prompt", text))

    config = AgentConfig(
        runtime="pi",
        model=AgentModelConfig(
            provider="anthropic",
            name="claude-sonnet-4-5",
            api_key_env="ANTHROPIC_API_KEY",
        ),
    )
    monkeypatch.setattr("aitest_kit.agent.cli.load_agent_config", lambda _workspace: config)
    monkeypatch.setattr("aitest_kit.agent.cli.build_worker_environment", lambda _config: {"PATH": "/usr/bin"})
    monkeypatch.setattr("aitest_kit.agent.cli.default_worker_command", lambda: ["node", "worker.ts"])
    monkeypatch.setattr("aitest_kit.agent.cli.WorkerClient", FakeWorkerClient)

    result = CliRunner().invoke(
        agent_command,
        ["run", "--workspace", str(tmp_path), "--prompt", "inspect tests"],
    )

    assert result.exit_code == 0
    start_payload = next(call[1] for call in calls if call[0] == "start")
    assert start_payload["model"]["api_key_env"] == "ANTHROPIC_API_KEY"
    assert start_payload["permission_mode"] == "approval"
    assert ("prompt", "inspect tests") in calls
    assert calls[-1] == ("close",)
