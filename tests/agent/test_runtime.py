from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from aitest_kit.agent.runtime import (
    AgentRuntimeError,
    install_runtime,
    resolve_worker_dir,
    runtime_status,
)


SEED = Path(__file__).resolve().parents[2] / "aitest_kit" / "agent" / "runtime_seed" / "pi_worker"


def test_runtime_command_resolves_platform_launcher_before_spawn(tmp_path, monkeypatch):
    from aitest_kit.agent import runtime

    launcher = str(tmp_path / "Program Files" / "nodejs" / "npm.cmd")
    monkeypatch.setattr(runtime.shutil, "which", lambda tool: launcher if tool == "npm" else None)
    calls = []

    def spawn(command, **kwargs):
        calls.append((command, kwargs))
        if command[0] != launcher:
            raise FileNotFoundError("bare npm does not resolve the Windows launcher")
        return subprocess.CompletedProcess(command, 0, "11.0.0\n", "")

    monkeypatch.setattr(runtime.subprocess, "run", spawn)
    result = runtime._run_command(["npm", "--version"], tmp_path, 5)
    assert result.returncode == 0
    assert calls[0][0] == [launcher, "--version"]
    assert calls[0][1].get("shell", False) is False


def _copy_seed(tmp_path: Path) -> Path:
    seed = tmp_path / "seed"
    shutil.copytree(SEED, seed)
    return seed


def _successful_runner(command: list[str], cwd: Path, timeout: float) -> subprocess.CompletedProcess[str]:
    if command[0] == "node" and command[1:] == ["--version"]:
        return subprocess.CompletedProcess(command, 0, "v24.14.0\n", "")
    if command[0] == "npm" and command[1:] == ["--version"]:
        return subprocess.CompletedProcess(command, 0, "11.9.0\n", "")
    if command[0] == "npm" and command[1:] == ["config", "get", "registry"]:
        return subprocess.CompletedProcess(command, 0, "https://registry.npmjs.org/\n", "")
    if command[:2] == ["npm", "ci"]:
        package = json.loads((cwd / "package.json").read_text(encoding="utf-8"))
        for name in package["dependencies"]:
            (cwd / "node_modules" / name).mkdir(parents=True)
        return subprocess.CompletedProcess(command, 0, "installed\n", "")
    if command[0] == "node" and command[-1] == "--self-test":
        return subprocess.CompletedProcess(command, 0, '{"runtime":"pi","status":"ok"}\n', "")
    raise AssertionError(f"unexpected command: {command}")


def test_install_runtime_is_atomic_and_idempotent(tmp_path: Path) -> None:
    seed = _copy_seed(tmp_path)
    home = tmp_path / "runtime-home"

    first = install_runtime(seed_dir=seed, runtime_home_dir=home, command_runner=_successful_runner)
    second = install_runtime(seed_dir=seed, runtime_home_dir=home, command_runner=_successful_runner)

    destination = Path(first["runtime_dir"])
    assert destination.is_dir()
    assert json.loads((destination / "install-manifest.json").read_text())["node_version"] == "v24.14.0"
    assert first["installed"] is True
    assert second["installed"] is False
    assert not list((home / "pi-worker").glob(".staging-*"))


def test_failed_setup_cleans_staging_and_preserves_existing_target(tmp_path: Path) -> None:
    seed = _copy_seed(tmp_path)
    manifest = json.loads((seed / "runtime-manifest.json").read_text())
    home = tmp_path / "runtime-home"
    destination = home / "pi-worker" / manifest["bundle_hash"]
    destination.mkdir(parents=True)
    marker = destination / "keep-me"
    marker.write_text("existing", encoding="utf-8")

    def failing_runner(command: list[str], cwd: Path, timeout: float) -> subprocess.CompletedProcess[str]:
        if command[:2] == ["npm", "ci"]:
            return subprocess.CompletedProcess(command, 1, "", "registry unavailable")
        return _successful_runner(command, cwd, timeout)

    with pytest.raises(AgentRuntimeError, match="npm ci") as caught:
        install_runtime(seed_dir=seed, runtime_home_dir=home, command_runner=failing_runner)

    assert caught.value.code == "AGENT_RUNTIME_INSTALL_FAILED"
    assert marker.read_text(encoding="utf-8") == "existing"
    assert not list((home / "pi-worker").glob(".staging-*"))


def test_successful_setup_replaces_an_invalid_existing_target(tmp_path: Path) -> None:
    seed = _copy_seed(tmp_path)
    manifest = json.loads((seed / "runtime-manifest.json").read_text())
    home = tmp_path / "runtime-home"
    destination = home / "pi-worker" / manifest["bundle_hash"]
    destination.mkdir(parents=True)
    (destination / "incomplete").write_text("old", encoding="utf-8")

    result = install_runtime(seed_dir=seed, runtime_home_dir=home, command_runner=_successful_runner)

    assert result["installed"] is True
    assert not (destination / "incomplete").exists()
    assert (destination / "install-manifest.json").is_file()
    assert not list((home / "pi-worker").glob(".*.backup"))


def test_failed_setup_redacts_environment_secrets(monkeypatch, tmp_path: Path) -> None:
    seed = _copy_seed(tmp_path)
    secret = "private-registry-token-value"
    monkeypatch.setenv("PRIVATE_NPM_TOKEN", secret)

    def leaking_runner(command: list[str], cwd: Path, timeout: float) -> subprocess.CompletedProcess[str]:
        if command[:2] == ["npm", "ci"]:
            return subprocess.CompletedProcess(command, 1, "", f"registry rejected {secret}")
        return _successful_runner(command, cwd, timeout)

    with pytest.raises(AgentRuntimeError) as caught:
        install_runtime(
            seed_dir=seed,
            runtime_home_dir=tmp_path / "runtime-home",
            command_runner=leaking_runner,
        )

    assert secret not in str(caught.value)
    assert "[REDACTED]" in str(caught.value)


def test_runtime_status_reports_node_failures_without_installing(tmp_path: Path) -> None:
    seed = _copy_seed(tmp_path)

    def missing_node(command: list[str], cwd: Path, timeout: float) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(command[0])

    status = runtime_status(
        seed_dir=seed,
        source_dir=tmp_path / "no-source",
        runtime_home_dir=tmp_path / "runtime-home",
        command_runner=missing_node,
    )

    assert status["state"] == "node_missing"
    assert status["source"] is None
    assert status["setup_command"] == "aitest agent setup"
    assert not (tmp_path / "runtime-home").exists()


def test_resolver_prefers_ready_source_then_user_runtime(tmp_path: Path) -> None:
    seed = _copy_seed(tmp_path)
    source = tmp_path / "source"
    shutil.copytree(seed, source)
    for name in json.loads((source / "package.json").read_text())["dependencies"]:
        (source / "node_modules" / name).mkdir(parents=True)
    home = tmp_path / "runtime-home"
    installed = install_runtime(seed_dir=seed, runtime_home_dir=home, command_runner=_successful_runner)

    assert resolve_worker_dir(seed_dir=seed, source_dir=source, runtime_home_dir=home) == source
    shutil.rmtree(source / "node_modules")
    assert resolve_worker_dir(seed_dir=seed, source_dir=source, runtime_home_dir=home) == Path(installed["runtime_dir"])


def test_resolver_returns_actionable_missing_error(tmp_path: Path) -> None:
    seed = _copy_seed(tmp_path)

    with pytest.raises(AgentRuntimeError) as caught:
        resolve_worker_dir(
            seed_dir=seed,
            source_dir=tmp_path / "no-source",
            runtime_home_dir=tmp_path / "runtime-home",
        )

    assert caught.value.code == "AGENT_RUNTIME_NOT_INSTALLED"
    assert "aitest agent setup" in str(caught.value)


def test_resolver_rejects_tampered_installed_seed_file(tmp_path: Path) -> None:
    seed = _copy_seed(tmp_path)
    home = tmp_path / "runtime-home"
    installed = install_runtime(seed_dir=seed, runtime_home_dir=home, command_runner=_successful_runner)
    (Path(installed["runtime_dir"]) / "src" / "worker.ts").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(AgentRuntimeError) as caught:
        resolve_worker_dir(
            seed_dir=seed,
            source_dir=tmp_path / "no-source",
            runtime_home_dir=home,
        )

    assert caught.value.code == "AGENT_RUNTIME_INVALID"


def test_resolver_rejects_tampered_installed_runtime_manifest(tmp_path: Path) -> None:
    seed = _copy_seed(tmp_path)
    home = tmp_path / "runtime-home"
    installed = install_runtime(seed_dir=seed, runtime_home_dir=home, command_runner=_successful_runner)
    manifest_path = Path(installed["runtime_dir"]) / "runtime-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["worker_version"] = "tampered"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(AgentRuntimeError) as caught:
        resolve_worker_dir(
            seed_dir=seed,
            source_dir=tmp_path / "no-source",
            runtime_home_dir=home,
        )

    assert caught.value.code == "AGENT_RUNTIME_INVALID"
