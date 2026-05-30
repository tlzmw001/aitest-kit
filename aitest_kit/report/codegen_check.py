"""Freshness check helpers for `aitest run`."""
from __future__ import annotations

import subprocess
import sys


def run_codegen_check(
    skip: bool,
    *,
    suite_file: str | None = None,
) -> dict[str, str]:
    if skip:
        return {"status": "skipped", "command": "", "message": "--skip-codegen-check"}

    if suite_file:
        cmd = [sys.executable, "-m", "aitest_kit.cli", "codegen", "--suite-file", suite_file]
        cmd.append("--check")
        completed = subprocess.run(cmd, text=True, capture_output=True)
        return _check_result(cmd, completed)

    return {
        "status": "failed",
        "command": "",
        "message": "suite_file is required for generated freshness check",
    }


def _check_result(cmd: list[str], completed: subprocess.CompletedProcess[str]) -> dict[str, str]:
    status = "passed" if completed.returncode == 0 else "failed"
    return {
        "status": status,
        "command": " ".join(cmd),
        "message": (completed.stdout + completed.stderr).strip(),
    }
