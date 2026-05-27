"""CLI commands for test execution reporting."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import click
import yaml

from aitest_kit.report.collector import blocked_result, collect_result
from aitest_kit.report.renderer import render_markdown
from aitest_kit.runtime_variables import (
    ProfileVariableError,
    dotenv_path,
    is_dotenv_configured,
    load_dotenv_values,
)
from aitest_kit.workspace import push_workspace


def _load_paths() -> tuple[Path, Path]:
    config_path = Path("aitest_config/config.yaml")
    if config_path.exists():
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        paths = cfg.get("paths", {}) if isinstance(cfg, dict) else {}
        generated_dir = Path(paths.get("generated_dir", "test_workspace/tests/generated"))
        reports_dir = Path(paths.get("reports_dir", "test_workspace/reports"))
        return generated_dir, reports_dir
    return Path("test_workspace/tests/generated"), Path("test_workspace/reports")


@click.command(
    name="run",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.option("--include-manual", is_flag=True, help="Include tests marked manual; excluded by default")
@click.option("--skip-codegen-check", is_flag=True, help="Skip generated freshness check before pytest")
@click.option("--workspace", type=click.Path(file_okay=False, dir_okay=True), help="Run from another AITest workspace root")
@click.argument("args", nargs=-1, type=click.UNPROCESSED, metavar="[MODULE]... [PYTEST_ARGS]...")
def run_command(
    include_manual: bool,
    skip_codegen_check: bool,
    workspace: str | None,
    args: tuple[str, ...],
):
    """Run generated pytest after freshness check and write structured reports.

    Examples:

      aitest run calibration

      aitest run calibration -- -k boundary
    """
    try:
        with push_workspace(workspace):
            _run_command_impl(include_manual, skip_codegen_check, args)
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise click.ClickException(str(exc)) from exc


def _run_command_impl(include_manual: bool, skip_codegen_check: bool, args: tuple[str, ...]) -> None:
    modules, extra_args = _split_args(args)
    generated_dir, reports_dir = _load_paths()
    files = _target_files(generated_dir, modules)
    run_id, run_dir = _create_run_dir(reports_dir)

    command = "aitest run" + (" " + " ".join(modules) if modules else "")
    manual_policy = "included" if include_manual else "excluded"
    try:
        pytest_env, environment = _pytest_environment()
    except _RunEnvironmentError as exc:
        result = blocked_result(
            run_id=run_id,
            command=command,
            codegen_check={"status": "skipped", "command": "", "message": ""},
            generated_files=files,
            manual_policy=manual_policy,
            blocked_reason="env_file",
            environment=exc.environment,
        )
        _write_result(run_dir, reports_dir, result)
        click.echo(f"BLOCKED_RUN: {exc}")
        raise SystemExit(10) from exc

    codegen_check = _codegen_check(modules, skip_codegen_check)
    if codegen_check["status"] == "failed":
        result = blocked_result(
            run_id=run_id,
            command=command,
            codegen_check=codegen_check,
            generated_files=files,
            manual_policy=manual_policy,
            environment=environment,
        )
        _write_result(run_dir, reports_dir, result)
        click.echo(f"BLOCKED_RUN: {codegen_check['message']}")
        raise SystemExit(10)

    if not files:
        result = collect_result(
            junit_path=None,
            generated_files=[],
            run_id=run_id,
            command=command,
            manual_policy=manual_policy,
            codegen_check=codegen_check,
            status="FAILED_RUN",
            environment=environment,
        )
        result["summary"]["error"] = 1
        _write_result(run_dir, reports_dir, result)
        click.echo("No generated test files found.")
        raise SystemExit(5)

    junit_path = run_dir / "junit.xml"
    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        *[str(path) for path in files],
        f"--junitxml={junit_path}",
        "-v",
    ]
    if not include_manual:
        pytest_cmd.extend(["-m", "not manual"])
    pytest_cmd.extend(extra_args)

    started = time.monotonic()
    completed = subprocess.run(pytest_cmd, text=True, env=pytest_env)
    duration = round(time.monotonic() - started, 3)

    result = collect_result(
        junit_path=junit_path,
        generated_files=files,
        run_id=run_id,
        command=command,
        duration_seconds=duration,
        manual_policy=manual_policy,
        codegen_check=codegen_check,
        environment=environment,
    )
    _write_result(run_dir, reports_dir, result)
    summary = result["summary"]
    click.echo(
        f"Report written: {run_dir / 'report.md'} "
        f"(passed={summary['passed']}, failed={summary['failed']}, error={summary['error']})"
    )
    raise SystemExit(completed.returncode)


@click.command(name="report")
@click.option("--workspace", type=click.Path(file_okay=False, dir_okay=True), help="Read reports from another AITest workspace root")
@click.argument("run_id", required=False)
def report_command(workspace: str | None, run_id: str | None):
    """Re-render report.md from an existing result.json."""
    try:
        with push_workspace(workspace):
            _report_command_impl(run_id)
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise click.ClickException(str(exc)) from exc


def _report_command_impl(run_id: str | None) -> None:
    _, reports_dir = _load_paths()
    result_path = (
        reports_dir / "runs" / run_id / "result.json"
        if run_id
        else reports_dir / "latest" / "result.json"
    )
    if not result_path.exists():
        raise click.ClickException(f"result.json not found: {result_path}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    report_path = result_path.parent / "report.md"
    report_path.write_text(render_markdown(result), encoding="utf-8")
    click.echo(f"Report written: {report_path}")


def _split_args(args: tuple[str, ...]) -> tuple[list[str], list[str]]:
    modules: list[str] = []
    extra: list[str] = []
    in_extra = False
    for arg in args:
        if arg.startswith("-"):
            in_extra = True
        if in_extra:
            extra.append(arg)
        else:
            modules.append(arg)
    return modules, extra


def _create_run_dir(reports_dir: Path, *, max_attempts: int = 10) -> tuple[str, Path]:
    for _ in range(max_attempts):
        run_id = _new_run_id()
        run_dir = reports_dir / "runs" / run_id
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        return run_id, run_dir
    raise click.ClickException("cannot allocate unique report run_id")


def _new_run_id() -> str:
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
    return f"{timestamp}-{uuid4().hex[:6]}"


class _RunEnvironmentError(Exception):
    def __init__(self, message: str, environment: dict) -> None:
        super().__init__(message)
        self.environment = environment


def _pytest_environment() -> tuple[dict[str, str], dict]:
    env = dict(os.environ)
    path = dotenv_path()
    configured = is_dotenv_configured()
    environment = {
        "env_file": str(path) if configured or path.exists() else "",
        "env_file_configured": configured,
        "env_file_loaded": False,
        "env_file_keys": [],
    }
    try:
        values = load_dotenv_values(strict_configured=True)
    except ProfileVariableError as exc:
        environment["env_file_error"] = str(exc)
        raise _RunEnvironmentError(str(exc), environment) from exc

    if values:
        for key, value in values.items():
            env.setdefault(key, value)
        environment["env_file"] = str(path)
        environment["env_file_loaded"] = True
        environment["env_file_keys"] = sorted(values)
    return env, environment


def _target_files(generated_dir: Path, modules: list[str]) -> list[Path]:
    if not modules:
        return sorted(generated_dir.glob("test_*.py"))
    files: list[Path] = []
    for module in modules:
        for category in ("business", "boundary"):
            path = generated_dir / f"test_{module}_{category}.py"
            if path.exists():
                files.append(path)
    return files


def _codegen_check(modules: list[str], skip: bool) -> dict[str, str]:
    if skip:
        return {"status": "skipped", "command": "", "message": "--skip-codegen-check"}

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
        return {"status": "failed", "command": " && ".join(commands), "message": "\n".join(messages).strip()}
    return {"status": "passed", "command": " && ".join(commands), "message": ""}


def _check_result(cmd: list[str], completed: subprocess.CompletedProcess[str]) -> dict[str, str]:
    status = "passed" if completed.returncode == 0 else "failed"
    return {
        "status": status,
        "command": " ".join(cmd),
        "message": (completed.stdout + completed.stderr).strip(),
    }


def _write_result(run_dir: Path, reports_dir: Path, result: dict) -> None:
    result_path = run_dir / "result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "report.md").write_text(render_markdown(result), encoding="utf-8")

    latest_dir = reports_dir / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(run_dir, latest_dir)
