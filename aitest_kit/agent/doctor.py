"""Diagnostics for the project-local Pi runtime."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aitest_kit.agent.client import WorkerClient, default_worker_command, default_worker_dir
from aitest_kit.agent.config import AgentConfigError, build_worker_environment, load_agent_config
from aitest_kit.agent.protocol import redact
from aitest_kit.agent.runtime import runtime_status


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    ok: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def run_agent_doctor(workspace: str | Path) -> list[DoctorCheck]:
    root = Path(workspace).expanduser().resolve()
    checks: list[DoctorCheck] = []
    status = runtime_status()
    node_ok = status["state"] not in {"node_missing", "node_unsupported"}
    node_message = status["message"] if not node_ok else (
        f"Node {status['node_version']}; required >= {status['minimum_node_version']}"
    )
    checks.append(DoctorCheck("node", node_ok, node_message))
    runtime_ok = status["state"] == "ready"
    checks.append(
        DoctorCheck(
            "runtime",
            runtime_ok,
            status["message"],
            details={
                "source": status["source"],
                "runtime_dir": status["runtime_dir"],
                "bundle_hash": status["bundle_hash"],
            },
        )
    )
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
    if not (node_ok and runtime_ok and key_exists):
        return checks
    worker_dir = default_worker_dir()
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
