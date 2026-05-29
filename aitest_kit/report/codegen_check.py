"""Freshness check helpers for `aitest run`."""
from __future__ import annotations

import subprocess
import sys


def run_codegen_check(
    modules: list[str],
    skip: bool,
    *,
    cases_path: str | None = None,
    suite_file: bool = False,
    module_override: str | None = None,
) -> dict[str, str]:
    if skip:
        return {"status": "skipped", "command": "", "message": "--skip-codegen-check"}

    if cases_path:
        option = "--suite-file" if suite_file else "--cases"
        cmd = [sys.executable, "-m", "aitest_kit.cli", "codegen", option, cases_path]
        if module_override:
            cmd.extend(["--module", module_override])
        cmd.append("--check")
        completed = subprocess.run(cmd, text=True, capture_output=True)
        return _check_result(cmd, completed)

    if not modules:
        cmd = [sys.executable, "-m", "aitest_kit.cli", "codegen", "--all", "--check"]
        completed = subprocess.run(cmd, text=True, capture_output=True)
        return _check_result(cmd, completed)

    messages: list[str] = []
    commands: list[str] = []
    for module in modules:
        cmd = [sys.executable, "-m", "aitest_kit.cli", "codegen", module, "--check"]
        commands.append(" ".join(cmd))
        completed = subprocess.run(cmd, text=True, capture_output=True)
        if completed.returncode:
            messages.append(completed.stdout + completed.stderr)
    if messages:
        return {
            "status": "failed",
            "command": " && ".join(commands),
            "message": "\n".join(messages).strip(),
        }
    return {"status": "passed", "command": " && ".join(commands), "message": ""}


def _check_result(cmd: list[str], completed: subprocess.CompletedProcess[str]) -> dict[str, str]:
    status = "passed" if completed.returncode == 0 else "failed"
    return {
        "status": status,
        "command": " ".join(cmd),
        "message": (completed.stdout + completed.stderr).strip(),
    }
