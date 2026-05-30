"""Build task contexts from target/module/all/case selectors."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable

import yaml

from aitest_kit.codegen.suite import parse_suite_case_file
from aitest_kit.registry.loader import load_module_context, load_suite_context, load_target_context
from aitest_kit.registry.models import TaskContext, TaskDefaults, TaskUnit
from aitest_kit.workspace_config import AITEST_CONFIG_PATH

TARGETS_CONFIG_PATH = Path("aitest_config/targets.yaml")


def build_task_context_from_selectors(
    *,
    target: str = "",
    module: str = "",
    all_suites: bool = False,
    case_ids: Iterable[str] = (),
) -> tuple[TaskContext | None, list[str]]:
    """Resolve CLI target/module/all selectors into an explicit task context."""
    requested_case_ids = _clean_case_ids(case_ids)
    diagnostics: list[str] = []

    if module and all_suites:
        diagnostics.append("E740: --module and --all are mutually exclusive")
        return None, diagnostics
    if not (target or module or all_suites):
        diagnostics.append("E740: selector requires --suite-file, --task-file, --target, --module, or --all")
        return None, diagnostics

    units = (
        _module_units(target, module, diagnostics)
        if module
        else _all_units(target, diagnostics)
    )
    if requested_case_ids:
        units, filter_diagnostics = _filter_units_by_case_ids(units, requested_case_ids)
        diagnostics.extend(filter_diagnostics)
    if diagnostics:
        return None, diagnostics
    if not units:
        diagnostics.append("E740: selector matched no active suites")
        return None, diagnostics

    task_name = _selector_task_name(target=target, module=module, all_suites=all_suites, case_ids=requested_case_ids)
    return TaskContext(
        workspace_root=Path.cwd().resolve(),
        task=task_name,
        task_path=Path(f"selector:{task_name}"),
        units=units,
        description=_selector_description(target=target, module=module, all_suites=all_suites, case_ids=requested_case_ids),
        defaults=TaskDefaults(),
        metadata={
            "selector": {
                "target": target,
                "module": module,
                "all_suites": all_suites,
                "case_ids": requested_case_ids,
            }
        },
        diagnostics=[],
    ), []


def filter_task_context_by_case_ids(
    task: TaskContext,
    case_ids: Iterable[str],
) -> tuple[TaskContext | None, list[str]]:
    """Return a task narrowed to units containing the requested case ids."""
    requested_case_ids = _clean_case_ids(case_ids)
    if not requested_case_ids:
        return task, []
    units, diagnostics = _filter_units_by_case_ids(task.units, requested_case_ids)
    if diagnostics:
        return None, diagnostics
    return replace(
        task,
        task=_selector_task_name(target="", module=task.task, all_suites=False, case_ids=requested_case_ids),
        units=units,
        metadata={**task.metadata, "case_ids": requested_case_ids},
    ), []


def _module_units(target: str, module: str, diagnostics: list[str]) -> list[TaskUnit]:
    if not module:
        diagnostics.append("E740: --module requires a module name")
        return []
    targets = [target] if target else _targets_containing_module(module)
    if not targets:
        diagnostics.append(f"E740: module not found in target registry: {module}")
        return []
    if len(targets) > 1:
        diagnostics.append(
            f"E740: module {module} exists in multiple targets; pass --target "
            + ", ".join(sorted(targets))
        )
        return []
    target_context = load_target_context(targets[0])
    if target_context.diagnostics:
        diagnostics.extend(target_context.diagnostics)
        return []
    module_context = load_module_context(target_context, module)
    diagnostics.extend(module_context.diagnostics)
    return _units_from_module(module_context)


def _all_units(target: str, diagnostics: list[str]) -> list[TaskUnit]:
    target_names = [target] if target else _discover_target_names()
    if not target_names:
        diagnostics.append("E740: no targets found in target registry")
        return []
    units: list[TaskUnit] = []
    for target_name in target_names:
        target_context = load_target_context(target_name)
        if target_context.diagnostics:
            diagnostics.extend(target_context.diagnostics)
            continue
        module_dir = target_context.defaults.module_dir
        if not module_dir.exists():
            diagnostics.append(f"E740: target module_dir not found: {module_dir}")
            continue
        for module_file in sorted(module_dir.glob("*.yaml")):
            module_context = load_module_context(target_context, module_file)
            diagnostics.extend(module_context.diagnostics)
            units.extend(_units_from_module(module_context))
    return units


def _units_from_module(module_context) -> list[TaskUnit]:
    units: list[TaskUnit] = []
    for registered in module_context.registered_suites:
        if registered.status != "active":
            continue
        units.append(TaskUnit(
            target=module_context.target,
            name=registered.suite,
            module=module_context.module,
            suite=registered.suite,
            suite_file=registered.manifest,
        ))
    return units


def _discover_target_names() -> list[str]:
    names: set[str] = set()
    targets_root = Path("test_workspace/targets")
    if targets_root.exists():
        names.update(path.parent.name for path in targets_root.glob("*/target.yaml"))
    if AITEST_CONFIG_PATH.exists():
        data = yaml.safe_load(AITEST_CONFIG_PATH.read_text(encoding="utf-8")) or {}
        raw_targets = data.get("targets", {})
        if isinstance(raw_targets, dict):
            names.update(str(name) for name in raw_targets if str(name).strip())
    if TARGETS_CONFIG_PATH.exists():
        data = yaml.safe_load(TARGETS_CONFIG_PATH.read_text(encoding="utf-8")) or {}
        raw_targets = data.get("targets", {})
        if isinstance(raw_targets, dict):
            names.update(str(name) for name in raw_targets if str(name).strip())
    return sorted(names)


def _targets_containing_module(module: str) -> list[str]:
    result: list[str] = []
    for target in _discover_target_names():
        target_context = load_target_context(target)
        if target_context.diagnostics:
            continue
        if (target_context.defaults.module_dir / f"{module}.yaml").exists():
            result.append(target)
    return result


def _filter_units_by_case_ids(
    units: list[TaskUnit],
    case_ids: list[str],
) -> tuple[list[TaskUnit], list[str]]:
    filtered: list[TaskUnit] = []
    diagnostics: list[str] = []
    requested = set(case_ids)
    for unit in units:
        if unit.suite_file is None:
            continue
        suite = load_suite_context(unit.suite_file)
        if suite.diagnostics:
            diagnostics.extend(suite.diagnostics)
            continue
        suite_case_ids = _suite_case_ids(suite.case_files, suite.module)
        allowed = set(unit.case_ids) if unit.case_ids else requested
        matches = sorted(requested & allowed & suite_case_ids)
        if matches:
            filtered.append(replace(unit, case_ids=matches))
    if not filtered:
        diagnostics.append("E740: requested case_id(s) not found in selected suites: " + ", ".join(case_ids))
    return filtered, diagnostics


def _suite_case_ids(case_files: list[Path], module: str) -> set[str]:
    case_ids: set[str] = set()
    for path in case_files:
        parse_result = parse_suite_case_file(path, module)
        case_ids.update(tc.id for tc in parse_result.cases)
    return case_ids


def _clean_case_ids(case_ids: Iterable[str]) -> list[str]:
    return [case_id.strip() for case_id in case_ids if isinstance(case_id, str) and case_id.strip()]


def _selector_task_name(
    *,
    target: str,
    module: str,
    all_suites: bool,
    case_ids: list[str],
) -> str:
    if module:
        base = f"{target}_{module}" if target else module
    elif target:
        base = f"{target}_all"
    elif all_suites:
        base = "all"
    else:
        base = "selected"
    if case_ids:
        base += "_case_" + "_".join(case_id.lower().replace("-", "_") for case_id in case_ids)
    return _safe_name(base)


def _selector_description(
    *,
    target: str,
    module: str,
    all_suites: bool,
    case_ids: list[str],
) -> str:
    parts = ["selector-derived task"]
    if target:
        parts.append(f"target={target}")
    if module:
        parts.append(f"module={module}")
    if all_suites:
        parts.append("all=true")
    if case_ids:
        parts.append("case_ids=" + ",".join(case_ids))
    return "; ".join(parts)


def _safe_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value)
    return cleaned.strip("_") or "selected"
