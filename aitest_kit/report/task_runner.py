"""Task-level execution for one or more suite manifests."""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import click

from aitest_kit.codegen.suite import (
    load_suite_context_for_paths,
    resolve_suite_runtime_paths,
)
from aitest_kit.registry import load_task_context
from aitest_kit.registry.models import TaskContext, TaskUnit


def run_task_command_impl(
    include_manual: bool,
    skip_codegen_check: bool,
    task_file: str,
    extra_args: list[str],
) -> None:
    """Run each suite unit in a task, then write a task-level aggregate report."""
    from aitest_kit.report.cli import _create_run_dir, _load_paths, _run_command_impl, _write_result

    task = load_task_context(task_file)
    if task.diagnostics:
        click.echo(f"Task: {task.task}")
        click.echo("Task manifest diagnostics:")
        for diagnostic in task.diagnostics:
            click.echo(f"  {diagnostic}")
        raise SystemExit(1)
    if not task.units:
        click.echo(f"Task {task.task} has no units")
        raise SystemExit(1)

    task_reports_dir = _load_paths().reports_dir / "tasks" / task.task
    task_run_id, task_run_dir = _create_run_dir(task_reports_dir)
    started = time.monotonic()
    unit_results: list[dict[str, Any]] = []
    exit_code = 0

    click.echo(f"Task: {task.task}")
    for index, unit in enumerate(task.units, start=1):
        result, code = _run_task_unit(
            task,
            unit,
            index,
            include_manual,
            skip_codegen_check,
            extra_args,
            _run_command_impl,
        )
        unit_results.append(result)
        if code:
            exit_code = code

    aggregate = _task_result(
        task,
        run_id=task_run_id,
        duration_seconds=round(time.monotonic() - started, 3),
        unit_results=unit_results,
        exit_code=exit_code,
        include_manual=include_manual,
    )
    _write_result(task_run_dir, task_reports_dir, aggregate)
    summary = aggregate["summary"]
    click.echo(
        f"Task report written: {task_run_dir / 'report.md'} "
        f"(passed={summary['passed']}, failed={summary['failed']}, error={summary['error']})"
    )
    raise SystemExit(exit_code)


def _run_task_unit(
    task: TaskContext,
    unit: TaskUnit,
    index: int,
    include_manual: bool,
    skip_codegen_check: bool,
    extra_args: list[str],
    run_suite,
) -> tuple[dict[str, Any], int]:
    if unit.all:
        click.echo(f"\n[{index}] target all is not supported in this phase: {unit.target}")
        return _synthetic_unit_result(task, unit, index, "target all is not supported"), 2
    if unit.suite_file is None:
        click.echo(f"\n[{index}] task unit requires suite_file")
        return _synthetic_unit_result(task, unit, index, "task unit requires suite_file"), 2

    unit_args = tuple(
        task.defaults.pytest_args
        + unit.pytest_args
        + extra_args
        + _case_id_filter_args(unit.case_ids)
    )
    unit_include_manual = _unit_include_manual(include_manual, task.defaults.include_manual, unit)
    label = unit.name or unit.suite or str(unit.suite_file)
    click.echo(f"\n[{index}] suite_file: {unit.suite_file}")
    if label:
        click.echo(f"    unit: {label}")

    try:
        run_suite(
            unit_include_manual,
            skip_codegen_check,
            unit_args,
            suite_file=str(unit.suite_file),
            env_files=task.env_files,
        )
        code = 0
    except SystemExit as exc:
        code = int(exc.code or 0)

    result = _read_unit_latest_result(unit)
    if result is None:
        result = _synthetic_unit_result(task, unit, index, "unit report was not written")
        code = code or 1
    result.setdefault("task_unit", _unit_payload(unit, index))
    return result, code


def _read_unit_latest_result(unit: TaskUnit) -> dict[str, Any] | None:
    if unit.suite_file is None:
        return None
    from aitest_kit.report.cli import _load_paths

    paths = _load_paths()
    context = load_suite_context_for_paths(
        str(unit.suite_file),
        module_override=unit.module or None,
        profile_dir=paths.profile_dir,
    )
    runtime_paths = resolve_suite_runtime_paths(
        context,
        generated_dir=paths.generated_dir,
        reports_dir=paths.reports_dir,
        profile_dir=paths.profile_dir,
    )
    result_path = runtime_paths.reports_dir / "latest" / "result.json"
    if not result_path.exists():
        return None
    return json.loads(result_path.read_text(encoding="utf-8"))


def _task_result(
    task: TaskContext,
    *,
    run_id: str,
    duration_seconds: float,
    unit_results: list[dict[str, Any]],
    exit_code: int,
    include_manual: bool,
) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    units: list[dict[str, Any]] = []
    modules: dict[str, Any] = {}
    summary = _empty_summary(duration_seconds)
    codegen_messages: list[str] = []
    codegen_commands: list[str] = []
    codegen_failed = False

    for index, result in enumerate(unit_results, start=1):
        units.append(_unit_result_payload(index, result))
        cases.extend(result.get("cases", []))
        skipped.extend(result.get("codegen_skipped_cases", []))
        _merge_summary(summary, result.get("summary", {}))
        _merge_modules(modules, result.get("modules", {}))
        check = result.get("codegen_check", {})
        if check.get("status") == "failed":
            codegen_failed = True
        if check.get("command"):
            codegen_commands.append(check["command"])
        if check.get("message"):
            codegen_messages.append(check["message"])

    summary["duration_seconds"] = duration_seconds
    return {
        "run_id": run_id,
        "status": "COMPLETED" if exit_code == 0 else "FAILED_RUN",
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "duration_seconds": duration_seconds,
        "command": f"aitest run --task-file {task.task_path}",
        "project_config_version": unit_results[0].get("project_config_version", "missing") if unit_results else "missing",
        "manual_policy": _task_manual_policy(task, include_manual),
        "environment": _aggregate_environment(unit_results),
        "codegen_check": {
            "status": "failed" if codegen_failed else "passed",
            "command": " && ".join(codegen_commands),
            "message": "\n".join(codegen_messages),
        },
        "task": {
            "name": task.task,
            "path": str(task.task_path),
            "description": task.description,
            "units": units,
        },
        "summary": summary,
        "modules": modules,
        "cases": cases,
        "codegen_skipped_cases": skipped,
    }


def _empty_summary(duration_seconds: float) -> dict[str, Any]:
    return {
        "passed": 0,
        "failed": 0,
        "error": 0,
        "pytest_skipped": 0,
        "auto_collected": 0,
        "manual_total": 0,
        "manual_executed": 0,
        "manual_not_run": 0,
        "codegen_skipped": 0,
        "duration_seconds": duration_seconds,
    }


def _merge_summary(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key in [
        "passed",
        "failed",
        "error",
        "pytest_skipped",
        "auto_collected",
        "manual_total",
        "manual_executed",
        "manual_not_run",
        "codegen_skipped",
    ]:
        target[key] = target.get(key, 0) + int(source.get(key, 0) or 0)


def _merge_modules(target: dict[str, Any], source: dict[str, Any]) -> None:
    for module, categories in source.items():
        module_bucket = target.setdefault(module, {})
        for category, bucket in categories.items():
            category_bucket = module_bucket.setdefault(category, {})
            for key, value in bucket.items():
                if isinstance(value, (int, float)):
                    category_bucket[key] = category_bucket.get(key, 0) + value
                else:
                    category_bucket[key] = value


def _aggregate_environment(results: list[dict[str, Any]]) -> dict[str, Any]:
    environments = [result.get("environment", {}) for result in results if result.get("environment")]
    if not environments:
        return {}
    env_files: list[str] = []
    keys: set[str] = set()
    for environment in environments:
        for path in environment.get("env_files", []):
            if path not in env_files:
                env_files.append(path)
        if environment.get("env_file") and environment.get("env_file") not in env_files:
            env_files.append(environment["env_file"])
        keys.update(environment.get("env_file_keys", []))
    return {
        "env_file": ":".join(env_files),
        "env_files": env_files,
        "env_file_configured": any(item.get("env_file_configured") for item in environments),
        "env_file_loaded": any(item.get("env_file_loaded") for item in environments),
        "env_file_keys": sorted(keys),
    }


def _unit_result_payload(index: int, result: dict[str, Any]) -> dict[str, Any]:
    payload = dict(result.get("task_unit", {"index": index}))
    payload.update({
        "run_id": result.get("run_id", ""),
        "status": result.get("status", ""),
        "summary": result.get("summary", {}),
    })
    return payload


def _synthetic_unit_result(task: TaskContext, unit: TaskUnit, index: int, message: str) -> dict[str, Any]:
    return {
        "run_id": f"{task.task}-unit-{index}",
        "status": "FAILED_RUN",
        "command": f"aitest run --task-file {task.task_path}",
        "summary": {**_empty_summary(0.0), "error": 1},
        "modules": {},
        "cases": [],
        "codegen_skipped_cases": [],
        "codegen_check": {"status": "failed", "command": "", "message": message},
        "task_unit": _unit_payload(unit, index),
    }


def _unit_payload(unit: TaskUnit, index: int) -> dict[str, Any]:
    return {
        "index": index,
        "name": unit.name,
        "target": unit.target,
        "module": unit.module,
        "suite": unit.suite,
        "suite_file": str(unit.suite_file) if unit.suite_file else "",
        "case_ids": unit.case_ids,
    }


def _task_manual_policy(task: TaskContext, cli_include_manual: bool) -> str:
    values = {
        _unit_include_manual(cli_include_manual, task.defaults.include_manual, unit)
        for unit in task.units
    }
    if values == {True}:
        return "included"
    if values == {False}:
        return "excluded"
    return "mixed"


def _unit_include_manual(cli_include_manual: bool, default_include_manual: bool | None, unit: TaskUnit) -> bool:
    if unit.include_manual is not None:
        return unit.include_manual
    if default_include_manual is not None:
        return default_include_manual
    return cli_include_manual


def _case_id_filter_args(case_ids: list[str]) -> list[str]:
    if not case_ids:
        return []
    terms = [case_id.lower().replace("-", "_") for case_id in case_ids]
    return ["-k", " or ".join(terms)]
