"""Delivery tooling contracts; no network or timing thresholds in unit tests."""
import importlib.util
import io
import struct
import json
import re
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROJECT_VERSION = re.search(r'^version = "([^"]+)"$', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)
REMOVED_AGENT_PATHS = (
    "aitest_kit/agent/runtime.py",
    "aitest_kit/console/agent_sessions.py",
    "agent_runtime/pi_worker/src/worker.ts",
    "aitest_kit/agent/runtime_seed/pi_worker/package-lock.json",
    "aitest_kit/console/web/assets/AgentView-old.js",
    "aitest_kit/console/web/assets/AgentConnectionView-old.css",
    "build/lib/node_modules/pi/package.json",
    "aitest_kit-0.5.0.data/purelib/aitest_kit/agent/config.py",
    "aitest_kit\\console\\agent_runtime.py",
)


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("platform", ["darwin", "linux"])
@pytest.mark.parametrize("name,size", [
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
    assert "AITEST_RUNTIME_HOME" not in env
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


def test_console_token_extraction_is_fragment_only():
    module = load_script("wheel_install_probe")
    assert module.session_token("Session URL: http://127.0.0.1:42/?launch=once#token=local") == "local"
    assert module.session_token("http://127.0.0.1:42/?token=do-not-use") is None


def test_probe_diagnostics_keep_errors_without_launch_credentials():
    module = load_script("wheel_install_probe")
    output = 'Session URL: http://localhost/#token=private\nAPI_KEY=private\nAttributeError: app has no add_event_handler\n'
    rendered = module.safe_diagnostic(output)
    assert 'AttributeError' in rendered
    assert 'private' not in rendered
    assert 'token' not in rendered


def test_install_failure_report_does_not_expose_subprocess_output(tmp_path, monkeypatch, capsys):
    module = load_script("verify_wheel_install")
    make_archive(tmp_path, "-py3-none-any.whl", ["aitest_kit/__init__.py"])
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


def test_install_ci_covers_all_platforms_without_node_runtime():
    import yaml

    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    job = workflow["jobs"]["install-smoke"]
    assert job["strategy"]["matrix"] == {
        "os": ["ubuntu-latest", "macos-latest", "windows-latest"],
    }
    assert not any("setup-node" in step.get("uses", "") for step in job["steps"])
    assert any("scripts/verify_wheel_install.py" in step.get("run", "") for step in job["steps"])
    assert any(step.get("if") == "always()" and step.get("uses", "").startswith("actions/upload-artifact@")
               for step in job["steps"])


def make_archive(directory, kind, members):
    path = directory / f"aitest_kit-0.5.0{kind}"
    if kind == "-py3-none-any.whl":
        with zipfile.ZipFile(path, "w") as archive:
            for name in members:
                archive.writestr(name, "fixture")
    else:
        with tarfile.open(path, "w:gz") as archive:
            for name in members:
                info = tarfile.TarInfo(f"aitest_kit-0.5.0/{name}")
                info.size = len(b"fixture")
                archive.addfile(info, io.BytesIO(b"fixture"))
    return path


@pytest.mark.parametrize("kind", ["-py3-none-any.whl", ".tar.gz"])
@pytest.mark.parametrize("removed_path", REMOVED_AGENT_PATHS)
def test_distribution_rejects_removed_agent_files(tmp_path, kind, removed_path):
    module = load_script("verify_wheel_install")
    archive = make_archive(tmp_path, kind, [removed_path])
    with pytest.raises(ValueError, match="clean checkout"):
        module.verify_archive(archive)


@pytest.mark.parametrize("kind", ["-py3-none-any.whl", ".tar.gz"])
def test_distribution_retains_console_and_neutral_skills(tmp_path, kind):
    module = load_script("verify_wheel_install")
    archive = make_archive(tmp_path, kind, [
        "aitest_kit/console/app.py",
        "aitest_kit/console/web/assets/DiffEditor-current.js",
        "aitest_kit/console/web/assets/editor.worker-current.js",
        "aitest_kit/templates/project_workspace/AGENTS.md",
        "aitest_kit/templates/project_workspace/skills/test-codegen/SKILL.md",
    ])
    module.verify_archive(archive)


def test_unreadable_wheel_fails_before_installation(tmp_path, monkeypatch, capsys):
    module = load_script("verify_wheel_install")
    (tmp_path / "aitest_kit-0.5.0-py3-none-any.whl").touch()
    output = tmp_path / "report.json"
    monkeypatch.setattr(module.sys, "argv", ["verify", "--wheel-dir", str(tmp_path), "--output", str(output)])

    def forbidden_run(*args, **kwargs):
        pytest.fail("Unreadable wheels must not reach subprocess execution")

    monkeypatch.setattr(module.subprocess, "run", forbidden_run)
    assert module.main() == 1
    report = json.loads(output.read_text())
    assert report["stage"] == "inspect_wheel"
    assert report["error_type"] == "BadZipFile"
    assert "embedded_agent" not in report
    assert "clean checkout" in capsys.readouterr().out


def test_install_rejects_contaminated_wheel_before_any_subprocess(tmp_path, monkeypatch, capsys):
    module = load_script("verify_wheel_install")
    make_archive(tmp_path, "-py3-none-any.whl", [REMOVED_AGENT_PATHS[0]])
    output = tmp_path / "report.json"
    monkeypatch.setattr(module.sys, "argv", ["verify", "--wheel-dir", str(tmp_path), "--output", str(output)])
    calls = []

    def would_pass(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps({
            "status": "passed", "console_http": "passed", "agent_api": "absent",
        }))

    monkeypatch.setattr(module.subprocess, "run", would_pass)
    assert module.main() == 1
    report = json.loads(output.read_text())
    assert report["stage"] == "inspect_wheel"
    assert report["error_type"] == "ValueError"
    assert "clean checkout" in report["diagnostic"]
    assert "embedded_agent" not in report
    assert calls == []
    assert REMOVED_AGENT_PATHS[0] not in output.read_text() + capsys.readouterr().out


@pytest.mark.parametrize("workflow,step_name", [
    ("ci.yml", "Inspect release artifacts"),
    ("publish.yml", "Inspect embedded Agent removal"),
])
def test_artifact_upload_gates_reuse_distribution_inspection(workflow, step_name):
    import yaml

    content = yaml.safe_load((ROOT / ".github/workflows" / workflow).read_text())
    steps = [step for job in content["jobs"].values() for step in job["steps"]]
    step = next(step for step in steps if step.get("name") == step_name)
    assert 'runpy.run_path("scripts/verify_wheel_install.py")["verify_archive"]' in step["run"]
    assert "verify_archive(wheel)" in step["run"]
    assert "verify_archive(sdist)" in step["run"]


@pytest.mark.parametrize("prefix", ["", "aitest_kit/templates/project_workspace/"])
def test_configuration_reference_does_not_prescribe_retired_agent_fields(prefix):
    content = (ROOT / prefix / "aitest_config/refs/config-files.md").read_text()
    table = content.split("## 字段归属表", 1)[1].split("\n## ", 1)[0]
    assert "aitest.yaml.agent" not in table
    assert "当前 Console/CLI 不消费这些字段" in content


def test_package_version_has_a_changelog_entry():
    assert f"## {PROJECT_VERSION} - " in (ROOT / "CHANGELOG.md").read_text()


def test_agent_removal_release_notes_explain_data_preservation():
    content = (ROOT / "CHANGELOG.md").read_text()
    heading = "## 0.6.0 - "
    assert heading in content
    notes = content.split(heading, 1)[1].split("\n## ", 1)[0]
    for contract in ("aitest agent", "/api/agent/*", "Runtime", "session", "v0.5.0"):
        assert contract in notes


@pytest.mark.parametrize("name", ["README.md", "README.en.md"])
def test_readme_describes_current_pypi_release_without_embedded_agent(name):
    content = (ROOT / name).read_text()
    installation = content.split("### 1.", 1)[1].split("### 2.", 1)[0]
    assert PROJECT_VERSION in installation
    assert 'python3 -m pip install -U "aitest-kit[server]"' in installation
    assert "尚未发布" not in installation
    assert "not released yet" not in installation
