"""CLI commands for test execution reporting."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import click

from aitest_kit.report.codegen_check import run_codegen_check
from aitest_kit.report.collector import blocked_result, collect_result
from aitest_kit.report.renderer import render_markdown
from aitest_kit.runtime_variables import (
    ProfileVariableError,
    dotenv_path,
    is_dotenv_configured,
    load_dotenv_values,
)
from aitest_kit.codegen.suite import (
    load_suite_context_for_paths,
    resolve_suite_runtime_paths,
    suite_generated_path,
)
from aitest_kit.report.task_runner import run_task_command_impl
from aitest_kit.workspace import push_workspace
from aitest_kit.workspace_config import load_workspace_paths


@dataclass(frozen=True)
class ReportPaths:
    generated_dir: Path
    reports_dir: Path
    profile_dir: Path


def _load_paths() -> ReportPaths:
    paths = load_workspace_paths()
    return ReportPaths(paths.generated_dir, paths.reports_dir, paths.profile_dir)


@click.command(
    name="run",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.option("--include-manual", is_flag=True, help="Include tests marked manual; excluded by default")
@click.option("--skip-codegen-check", is_flag=True, help="Skip generated freshness check before pytest")
@click.option("--cases", "cases_path", type=click.Path(file_okay=False, dir_okay=True), help="Run generated tests for one case suite directory")
@click.option("--suite-file", type=click.Path(file_okay=True, dir_okay=False), help="Run generated tests for one suite manifest file")
@click.option(
    "--task-file",
    "--task",
    "task_file",
    type=click.Path(file_okay=True, dir_okay=False),
    help="Run generated tests for suites listed by one task manifest",
)
@click.option("--module", "module_option", help="Owning module for --cases when no aitest_suite.yaml is present")
@click.option("--workspace", type=click.Path(file_okay=False, dir_okay=True), help="Run from another AITest workspace root")
@click.argument("args", nargs=-1, type=click.UNPROCESSED, metavar="[MODULE]... [PYTEST_ARGS]...")
def run_command(
    include_manual: bool,
    skip_codegen_check: bool,
    cases_path: str | None,
    suite_file: str | None,
    task_file: str | None,
    module_option: str | None,
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
            _run_command_impl(
                include_manual,
                skip_codegen_check,
                args,
                cases_path=cases_path,
                suite_file=suite_file,
                task_file=task_file,
                module_override=module_option,
            )
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise click.ClickException(str(exc)) from exc


def _run_command_impl(
    include_manual: bool,
    skip_codegen_check: bool,
    args: tuple[str, ...],
    *,
    cases_path: str | None = None,
    suite_file: str | None = None,
    task_file: str | None = None,
    module_override: str | None = None,
    env_files: list[Path] | None = None,
) -> None:
    modules, extra_args = _split_args(args)
    suite_sources = [item for item in (cases_path, suite_file, task_file) if item]
    if len(suite_sources) > 1:
        click.echo("Error: --cases, --suite-file, and --task-file are mutually exclusive")
        raise SystemExit(2)
    if (suite_file or task_file) and module_override:
        click.echo("Error: --module can only be used with --cases")
        raise SystemExit(2)
    if (cases_path or suite_file or task_file) and modules:
        click.echo("Error: suite/task run cannot be combined with positional modules")
        raise SystemExit(2)
    if task_file:
        run_task_command_impl(
            include_manual,
            skip_codegen_check,
            task_file,
            extra_args,
        )
        return
    suite_source = suite_file or cases_path
    paths = _load_paths()
    suite_context = None
    if suite_source:
        suite_context = load_suite_context_for_paths(
            suite_source,
            module_override=module_override,
            profile_dir=paths.profile_dir,
        )
        suite_paths = resolve_suite_runtime_paths(
            suite_context,
            generated_dir=paths.generated_dir,
            reports_dir=paths.reports_dir,
            profile_dir=paths.profile_dir,
        )
        paths = ReportPaths(
            suite_paths.generated_dir,
            suite_paths.reports_dir,
            suite_paths.profile_dir,
        )
    files = _target_files(
        paths.generated_dir,
        modules,
        cases_path=suite_source,
        module_override=module_override,
        profile_dir=paths.profile_dir,
        suite_context=suite_context,
    )
    run_id, run_dir = _create_run_dir(paths.reports_dir)

    if suite_file:
        command = "aitest run --suite-file " + suite_file
    elif cases_path:
        command = "aitest run --cases " + cases_path
        if module_override:
            command += " --module " + module_override
    else:
        command = "aitest run" + (" " + " ".join(modules) if modules else "")
    manual_policy = "included" if include_manual else "excluded"
    try:
        pytest_env, environment = _pytest_environment(env_files=env_files)
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
        _write_result(run_dir, paths.reports_dir, result)
        click.echo(f"BLOCKED_RUN: {exc}")
        raise SystemExit(10) from exc

    codegen_check = run_codegen_check(
        modules,
        skip_codegen_check,
        cases_path=suite_source,
        suite_file=bool(suite_file),
        module_override=module_override,
    )
    if codegen_check["status"] == "failed":
        result = blocked_result(
            run_id=run_id,
            command=command,
            codegen_check=codegen_check,
            generated_files=files,
            manual_policy=manual_policy,
            environment=environment,
        )
        _write_result(run_dir, paths.reports_dir, result)
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
        _write_result(run_dir, paths.reports_dir, result)
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
    _write_result(run_dir, paths.reports_dir, result)
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
    paths = _load_paths()
    result_path = (
        paths.reports_dir / "runs" / run_id / "result.json"
        if run_id
        else paths.reports_dir / "latest" / "result.json"
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


def _pytest_environment(env_files: list[Path] | None = None) -> tuple[dict[str, str], dict]:
    env = dict(os.environ)
    explicit_env_files = list(env_files or [])
    path = dotenv_path()
    configured = bool(explicit_env_files) or is_dotenv_configured()
    env_file_display = (
        os.pathsep.join(str(path) for path in explicit_env_files)
        if explicit_env_files
        else str(path) if configured or path.exists() else ""
    )
    environment = {
        "env_file": env_file_display,
        "env_file_configured": configured,
        "env_file_loaded": False,
        "env_file_keys": [],
    }
    if explicit_env_files:
        environment["env_files"] = [str(path) for path in explicit_env_files]
    try:
        values = load_dotenv_values(
            strict_configured=True,
            paths=explicit_env_files or None,
        )
    except ProfileVariableError as exc:
        environment["env_file_error"] = str(exc)
        raise _RunEnvironmentError(str(exc), environment) from exc

    if values:
        for key, value in values.items():
            env.setdefault(key, value)
        if not explicit_env_files:
            environment["env_file"] = str(path)
        environment["env_file_loaded"] = True
        environment["env_file_keys"] = sorted(values)
    return env, environment


def _target_files(
    generated_dir: Path,
    modules: list[str],
    *,
    cases_path: str | None = None,
    module_override: str | None = None,
    profile_dir: Path | None = None,
    suite_context=None,
) -> list[Path]:
    if cases_path:
        context = suite_context or load_suite_context_for_paths(
            cases_path,
            module_override=module_override,
            profile_dir=profile_dir or "test_workspace/tests/fixtures",
        )
        return [
            suite_generated_path(generated_dir, context, path)
            for path in context.case_files
            if context.module and context.suite
        ]
    if not modules:
        return sorted(generated_dir.glob("test_*.py"))
    files: list[Path] = []
    for module in modules:
        for category in ("business", "boundary"):
            path = generated_dir / f"test_{module}_{category}.py"
            if path.exists():
                files.append(path)
    return files


def _write_result(run_dir: Path, reports_dir: Path, result: dict) -> None:
    result_path = run_dir / "result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "report.md").write_text(render_markdown(result), encoding="utf-8")

    latest_dir = reports_dir / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(run_dir, latest_dir)
