"""Diagnostics for the project-local Pi runtime."""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aitest_kit.agent.client import WorkerClient, default_worker_command, default_worker_dir
from aitest_kit.agent.config import AgentConfigError, build_worker_environment, load_agent_config
from aitest_kit.agent.protocol import redact


MINIMUM_NODE_VERSION = (22, 19, 0)


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    ok: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def run_agent_doctor(workspace: str | Path) -> list[DoctorCheck]:
    root = Path(workspace).expanduser().resolve()
    worker_dir = default_worker_dir()
    checks: list[DoctorCheck] = []
    node_ok, node_message = _check_node()
    checks.append(DoctorCheck("node", node_ok, node_message))
    dependencies_ok, dependencies_message = _check_dependencies(worker_dir)
    checks.append(DoctorCheck("dependencies", dependencies_ok, dependencies_message))
    try:
        config = load_agent_config(root)
    except AgentConfigError as exc:
        checks.append(DoctorCheck("config", False, str(exc)))
        return checks
    checks.append(
        DoctorCheck(
            "config",
            True,
            f"Pi model: {config.model.provider}/{config.model.name}",
        )
    )
    key_exists = bool(os.environ.get(config.model.api_key_env))
    checks.append(
        DoctorCheck(
            "api_key_env",
            key_exists,
            f"{config.model.api_key_env} is {'set' if key_exists else 'not set'}",
        )
    )
    if not (node_ok and dependencies_ok and key_exists):
        return checks
    client = WorkerClient(
        default_worker_command(worker_dir),
        env=build_worker_environment(config),
        startup_timeout=15,
        shutdown_timeout=5,
    )
    try:
        client.start(
            {
                "cwd": str(root),
                "model": {
                    "provider": config.model.provider,
                    "name": config.model.name,
                    "protocol": config.model.protocol,
                    "api_key_env": config.model.api_key_env,
                    "base_url": config.model.base_url,
                    "base_url_env": config.model.base_url_env,
                },
                "skill_paths": [],
                "permission_mode": "approval",
            }
        )
        checks.append(DoctorCheck("worker", True, "worker handshake and shutdown succeeded"))
    except Exception as exc:  # noqa: BLE001 - doctor reports rather than hides runtime diagnostics.
        checks.append(DoctorCheck("worker", False, str(exc)))
    finally:
        client.close()
    return checks


def format_doctor_checks(checks: list[DoctorCheck]) -> str:
    lines: list[str] = []
    for check in checks:
        status = "OK" if check.ok else "FAIL"
        lines.append(f"[{status}] {check.name}: {check.message}")
        if check.details:
            lines.append(json.dumps(redact(check.details), ensure_ascii=False, sort_keys=True))
    return "\n".join(lines)


def _check_node() -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            ["node", "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Node.js unavailable: {exc}"
    raw = completed.stdout.strip()
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", raw)
    if completed.returncode != 0 or match is None:
        return False, f"cannot parse Node.js version: {raw or completed.stderr.strip()}"
    version = tuple(int(part) for part in match.groups())
    minimum = ".".join(str(part) for part in MINIMUM_NODE_VERSION)
    return version >= MINIMUM_NODE_VERSION, f"Node {raw}; required >= {minimum}"


def _check_dependencies(worker_dir: Path) -> tuple[bool, str]:
    lock_path = worker_dir / "package-lock.json"
    package_path = worker_dir / "package.json"
    if not package_path.is_file() or not lock_path.is_file():
        return False, f"missing package.json or package-lock.json under {worker_dir}"
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"cannot read Pi Worker package metadata: {exc}"
    expected = package.get("dependencies", {})
    locked = lock.get("packages", {}).get("", {}).get("dependencies", {})
    if expected != locked:
        return False, "package-lock root dependencies do not match package.json"
    missing = [name for name in expected if not (worker_dir / "node_modules" / name).exists()]
    if missing:
        return False, "npm dependencies not installed: " + ", ".join(sorted(missing))
    return True, "Pi Worker dependencies and lockfile are present"
