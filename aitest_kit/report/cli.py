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
from aitest_kit.report.collector import blocked_result, collect_result, generated_nodeids_for_case_ids
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
from aitest_kit.report.task_runner import run_task_command_impl, run_task_context_command_impl
from aitest_kit.registry import load_task_context
from aitest_kit.registry.selection import (
    build_task_context_from_selectors,
    filter_task_context_by_case_ids,
    suite_case_report_dir_name,
    task_report_dir_name,
)
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
@click.option("--suite-file", type=click.Path(file_okay=True, dir_okay=False), help="Run generated tests for one suite manifest file")
@click.option(
    "--task-file",
    "--task",
    "task_file",
    type=click.Path(file_okay=True, dir_okay=False),
    help="Run generated tests for suites listed by one task manifest",
)
@click.option("--target", help="Run active suites registered under one target")
@click.option("--module", "module_name", help="Run active suites registered under one module")
@click.option("--all", "all_suites", is_flag=True, help="Run all active suites in the registry")
@click.option("--case-id", "case_ids", multiple=True, help="Run one case id; can be repeated")
@click.option("--workspace", type=click.Path(file_okay=False, dir_okay=True), help="Run from another AITest workspace root")
@click.argument("args", nargs=-1, type=click.UNPROCESSED, metavar="[PYTEST_ARGS]...")
def run_command(
    include_manual: bool,
    skip_codegen_check: bool,
    suite_file: str | None,
    task_file: str | None,
    target: str | None,
    module_name: str | None,
    all_suites: bool,
    case_ids: tuple[str, ...],
    workspace: str | None,
    args: tuple[str, ...],
):
    """Run generated pytest after freshness check and write structured reports.

    Examples:

      aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml

      aitest run --suite-file test_workspace/suites/<target>/<suite>/suite.yaml -- -k boundary
    """
    try:
        with push_workspace(workspace):
            _run_command_impl(
                include_manual,
                skip_codegen_check,
                args,
                suite_file=suite_file,
                task_file=task_file,
                target=target,
                module_name=module_name,
                all_suites=all_suites,
                case_ids=case_ids,
            )
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise click.ClickException(str(exc)) from exc


def _run_command_impl(
    include_manual: bool,
    skip_codegen_check: bool,
    args: tuple[str, ...],
    *,
    suite_file: str | None = None,
    task_file: str | None = None,
    target: str | None = None,
    module_name: str | None = None,
    all_suites: bool = False,
    case_ids: tuple[str, ...] = (),
    env_files: list[Path] | None = None,
) -> None:
    extra_args = list(args)
    if suite_file and task_file:
        click.echo("Error: --suite-file and --task-file are mutually exclusive")
        raise SystemExit(2)
    selector_used = bool(target or module_name or all_suites)
    if selector_used and (suite_file or task_file):
        click.echo("Error: target/module/all selectors cannot be combined with --suite-file or --task-file")
        raise SystemExit(2)
    if not suite_file and not task_file and not selector_used:
        click.echo(
            "Usage: aitest run --suite-file <suite.yaml>, --task-file <task.yaml>, "
            "--target <target> [--module <module>], or --all"
        )
        raise SystemExit(2)
    if task_file:
        run_task_command_impl(
            include_manual,
            skip_codegen_check,
            task_file,
            extra_args,
            case_ids=list(case_ids),
        )
        return
    if selector_used:
        task, diagnostics = build_task_context_from_selectors(
            target=target or "",
            module=module_name or "",
            all_suites=all_suites,
            case_ids=case_ids,
        )
        if diagnostics or task is None:
            for diagnostic in diagnostics:
                click.echo(diagnostic)
            raise SystemExit(2)
        run_task_context_command_impl(
            task,
            include_manual=include_manual,
            skip_codegen_check=skip_codegen_check,
            extra_args=extra_args,
        )
        return
    paths = _load_paths()
    root_reports_dir = paths.reports_dir
    suite_context = load_suite_context_for_paths(
        suite_file,
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
        (
            root_reports_dir / "tasks" / suite_case_report_dir_name(
                target=suite_context.target,
                module=suite_context.module,
                suite=suite_context.suite,
                case_ids=case_ids,
            )
            if case_ids
            else suite_paths.reports_dir
        ),
        suite_paths.profile_dir,
    )
    files = _target_files(
        paths.generated_dir,
        suite_context=suite_context,
    )
    run_id, run_dir = _create_run_dir(paths.reports_dir)

    command = "aitest run --suite-file " + suite_file
    if case_ids:
        command += "".join(f" --case-id {case_id}" for case_id in case_ids)
    manual_policy = "included" if include_manual else "excluded"
    run_scope = _run_scope_payload(
        suite_context=suite_context,
        suite_file=suite_file,
        case_ids=case_ids,
    )
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
            run_scope=run_scope,
        )
        _write_result(run_dir, paths.reports_dir, result)
        click.echo(f"BLOCKED_RUN: {exc}")
        raise SystemExit(10) from exc

    codegen_check = run_codegen_check(
        skip_codegen_check,
        suite_file=suite_file,
    )
    if codegen_check["status"] == "failed":
        result = blocked_result(
            run_id=run_id,
            command=command,
            codegen_check=codegen_check,
            generated_files=files,
            manual_policy=manual_policy,
            environment=environment,
            run_scope=run_scope,
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
            run_scope=run_scope,
        )
        result["summary"]["error"] = 1
        _write_result(run_dir, paths.reports_dir, result)
        click.echo("No generated test files found.")
        raise SystemExit(5)

    selected_nodeids: list[str] = []
    if case_ids:
        selected_nodeids, missing_case_ids = generated_nodeids_for_case_ids(files, list(case_ids))
        if missing_case_ids:
            click.echo("Requested case_id(s) not found in generated pytest: " + ", ".join(missing_case_ids))
            raise SystemExit(5)

    junit_path = run_dir / "junit.xml"
    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        *(selected_nodeids or [str(path) for path in files]),
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
        run_scope=run_scope,
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
@click.option("--suite-file", type=click.Path(file_okay=True, dir_okay=False), help="Read reports for one suite manifest file")
@click.option(
    "--task-file",
    "--task",
    "task_file",
    type=click.Path(file_okay=True, dir_okay=False),
    help="Read reports for one task manifest",
)
@click.option("--target", help="Read reports for one target selector")
@click.option("--module", "module_name", help="Read reports for one module selector")
@click.option("--all", "all_suites", is_flag=True, help="Read reports for the all-suites selector")
@click.option("--case-id", "case_ids", multiple=True, help="Read reports for one case-filtered selector; can be repeated")
@click.argument("run_id", required=False)
def report_command(
    workspace: str | None,
    suite_file: str | None,
    task_file: str | None,
    target: str | None,
    module_name: str | None,
    all_suites: bool,
    case_ids: tuple[str, ...],
    run_id: str | None,
):
    """Re-render report.md from an existing result.json."""
    try:
        with push_workspace(workspace):
            _report_command_impl(
                run_id,
                suite_file=suite_file,
                task_file=task_file,
                target=target,
                module_name=module_name,
                all_suites=all_suites,
                case_ids=case_ids,
            )
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise click.ClickException(str(exc)) from exc


def _report_command_impl(
    run_id: str | None,
    *,
    suite_file: str | None = None,
    task_file: str | None = None,
    target: str | None = None,
    module_name: str | None = None,
    all_suites: bool = False,
    case_ids: tuple[str, ...] = (),
) -> None:
    if suite_file and task_file:
        raise click.ClickException("--suite-file and --task-file are mutually exclusive")
    selector_used = bool(target or module_name or all_suites)
    if selector_used and (suite_file or task_file):
        raise click.ClickException("target/module/all selectors cannot be combined with --suite-file or --task-file")
    paths = _load_paths()
    reports_dir = paths.reports_dir
    if suite_file:
        suite_context = load_suite_context_for_paths(
            suite_file,
            profile_dir=paths.profile_dir,
        )
        suite_paths = resolve_suite_runtime_paths(
            suite_context,
            generated_dir=paths.generated_dir,
            reports_dir=paths.reports_dir,
            profile_dir=paths.profile_dir,
        )
        reports_dir = (
            paths.reports_dir / "tasks" / suite_case_report_dir_name(
                target=suite_context.target,
                module=suite_context.module,
                suite=suite_context.suite,
                case_ids=case_ids,
            )
            if case_ids
            else suite_paths.reports_dir
        )
    elif task_file:
        task = load_task_context(task_file)
        if case_ids:
            task, diagnostics = filter_task_context_by_case_ids(task, case_ids)
            if diagnostics or task is None:
                raise click.ClickException("; ".join(diagnostics))
        if task.diagnostics:
            raise click.ClickException("; ".join(task.diagnostics))
        reports_dir = paths.reports_dir / "tasks" / task.task
    elif selector_used:
        reports_dir = paths.reports_dir / "tasks" / task_report_dir_name(
            target=target or "",
            module=module_name or "",
            all_suites=all_suites,
            case_ids=case_ids,
        )

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
    *,
    suite_context=None,
) -> list[Path]:
    if suite_context is None:
        return []
    return [
        suite_generated_path(generated_dir, suite_context, path)
        for path in suite_context.case_files
        if suite_context.module and suite_context.suite
    ]


def _run_scope_payload(
    *,
    suite_context,
    suite_file: str | None,
    case_ids: tuple[str, ...] = (),
) -> dict:
    if suite_context is not None:
        suite_manifest = suite_context.manifest_path
        suite_source = suite_manifest or Path(suite_file or "")
        payload = {
            "type": "suite_file",
            "target": suite_context.target,
            "module": suite_context.module,
            "suite": suite_context.suite,
            "suite_file": str(suite_source) if str(suite_source) != "." else "",
            "suite_dir": str(suite_context.suite_dir),
            "case_files": [str(path) for path in suite_context.case_files],
        }
        if case_ids:
            payload["case_ids"] = list(case_ids)
        return payload
    return {"type": "unknown"}


def _write_result(run_dir: Path, reports_dir: Path, result: dict) -> None:
    result_path = run_dir / "result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "report.md").write_text(render_markdown(result), encoding="utf-8")

    latest_dir = reports_dir / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(run_dir, latest_dir)
