"""Delivery tooling contracts; no network or timing thresholds in unit tests."""
import importlib.util
import struct
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("platform", ["darwin", "linux"])
@pytest.mark.parametrize("name,size", [
    ("agent-approval-workbench", (1440, 900)),
    ("editor-tab-close-hover", (34, 38)),
])
def test_reviewed_visual_baselines_exist(platform, name, size):
    path = ROOT / "console_web/e2e/__screenshots__/console.spec.ts" / f"{name}-{platform}.png"
    assert path.is_file(), f"Missing reviewed baseline: {path.name}"
    content = path.read_bytes()
    assert content[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", content[16:24]) == size


def test_install_environment_does_not_inherit_credentials(tmp_path):
    module = load_script("verify_wheel_install")
    env = module.clean_environment(tmp_path, {
        "PATH": "/bin", "SystemRoot": "C:\\Windows", "HOME": "/users/test",
        "OPENAI_API_KEY": "private", "PYTHONPATH": "/source", "NPM_TOKEN": "private",
        "AITEST_RUNTIME_HOME": "/real/user/runtime", "HTTPS_PROXY": "https://secret@proxy",
    })
    assert env["PATH"] == "/bin"
    assert env["HOME"] == "/users/test"
    assert env["SystemRoot"] == "C:\\Windows"
    assert env["AITEST_RUNTIME_HOME"] == str(tmp_path / "runtimes")
    for name in ("OPENAI_API_KEY", "PYTHONPATH", "NPM_TOKEN", "HTTPS_PROXY"):
        assert name not in env


def test_wheel_selection_rejects_ambiguous_artifacts(tmp_path):
    module = load_script("verify_wheel_install")
    with pytest.raises(ValueError):
        module.select_wheel(tmp_path)
    wheel = tmp_path / "aitest_kit-0.4.0-py3-none-any.whl"
    wheel.touch()
    assert module.select_wheel(tmp_path) == wheel
    (tmp_path / "aitest_kit-0.5.0-py3-none-any.whl").touch()
    with pytest.raises(ValueError):
        module.select_wheel(tmp_path)


def test_persistence_benchmark_uses_durable_writes_and_reopens(tmp_path):
    module = load_script("benchmark_agent_persistence")
    result = module.measure(tmp_path, count=3, payload_bytes=16)
    assert result["events"] == 3
    assert result["reopened_seq"] == 3
    assert result["metadata_seq"] == 3
    assert result["fsync_calls"] == 6
    assert result["journal_bytes"] > 3 * 16
    assert result["latency_ms"]["max"] >= result["latency_ms"]["p95"] >= result["latency_ms"]["p50"] >= 0


def test_console_token_extraction_is_fragment_only():
    module = load_script("wheel_install_probe")
    assert module.session_token("Session URL: http://127.0.0.1:42/?launch=once#token=local") == "local"
    assert module.session_token("http://127.0.0.1:42/?token=do-not-use") is None


def test_install_failure_report_does_not_expose_subprocess_output(tmp_path, monkeypatch, capsys):
    module = load_script("verify_wheel_install")
    (tmp_path / "aitest_kit-0.4.0-py3-none-any.whl").touch()
    output = tmp_path / "report.json"
    monkeypatch.setattr(module.sys, "argv", ["verify", "--wheel-dir", str(tmp_path), "--output", str(output)])

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["private-command"], output="token=private", stderr="secret")

    monkeypatch.setattr(module.subprocess, "run", fail)
    assert module.main() == 1
    report = json.loads(output.read_text())
    assert report["stage"] == "create_venv"
    assert report["error_type"] == "CalledProcessError"
    assert report["exit_code"] == 1
    assert "private" not in output.read_text() + capsys.readouterr().out


def test_install_ci_covers_all_platform_node_combinations():
    import yaml

    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    job = workflow["jobs"]["install-smoke"]
    assert job["strategy"]["matrix"] == {
        "os": ["ubuntu-latest", "macos-latest", "windows-latest"], "node": ["22.19.0", "24"],
    }
    assert any("scripts/verify_wheel_install.py" in step.get("run", "") for step in job["steps"])
    assert any(step.get("if") == "always()" and step.get("uses", "").startswith("actions/upload-artifact@")
               for step in job["steps"])
