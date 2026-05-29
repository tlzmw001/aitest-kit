"""Load task manifests for suite execution plans."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from aitest_kit.registry.models import TaskContext, TaskDefaults, TaskUnit
from aitest_kit.registry.path_resolver import resolve_path


def load_task_context(
    task_file: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> TaskContext:
    """Load a task manifest without executing it."""
    root = Path(workspace_root).expanduser().resolve()
    diagnostics: list[str] = []
    path = Path(task_file).expanduser()
    if not path.is_absolute():
        path = root / path
    path = path.resolve(strict=False)
    data = _read_yaml_mapping(path, diagnostics, "task")
    _validate_schema_version(data, diagnostics)
    task_name = _task_name(data, diagnostics) or path.stem
    description = data.get("description", "")
    if description is not None and not isinstance(description, str):
        diagnostics.append("E720: task description must be a string")
        description = ""
    env_files = _resolve_path_list(
        data.get("env_files", []),
        base_dir=path.parent,
        diagnostics=diagnostics,
        field="env_files",
    )
    defaults = _task_defaults(data.get("defaults", {}), diagnostics)
    units = _task_units(data.get("units", []), path.parent, diagnostics)

    return TaskContext(
        workspace_root=root,
        task=task_name,
        task_path=path,
        units=units,
        description=description or "",
        env_files=env_files,
        defaults=defaults,
        diagnostics=diagnostics,
    )


def _read_yaml_mapping(path: Path, diagnostics: list[str], label: str) -> dict[str, Any]:
    if not path.exists():
        diagnostics.append(f"E700: {label} config not found: {path}")
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        diagnostics.append(f"E700: {label} config is invalid YAML: {exc}")
        return {}
    if not isinstance(data, dict):
        diagnostics.append(f"E700: {label} config root must be a mapping")
        return {}
    return data


def _validate_schema_version(data: dict[str, Any], diagnostics: list[str]) -> None:
    value = data.get("schema_version")
    if value is None:
        return
    if value != 1:
        diagnostics.append("E720: task schema_version must be 1")


def _task_name(data: dict[str, Any], diagnostics: list[str]) -> str:
    task = data.get("task")
    name = data.get("name")
    if isinstance(task, str) and task.strip():
        return task.strip()
    if isinstance(name, str) and name.strip():
        return name.strip()
    diagnostics.append("E700: task name is required")
    return ""


def _task_units(value: Any, task_dir: Path, diagnostics: list[str]) -> list[TaskUnit]:
    units: list[TaskUnit] = []
    if not isinstance(value, list):
        diagnostics.append("E720: task units must be a list")
        return units
    for index, item in enumerate(value):
        units.append(_task_unit(item, task_dir, diagnostics, index))
    return units


def _task_unit(item: Any, task_dir: Path, diagnostics: list[str], index: int) -> TaskUnit:
    if not isinstance(item, dict):
        diagnostics.append(f"E721: units[{index}] must be a mapping")
        return TaskUnit(target="")
    target = item.get("target", "")
    if target is None:
        target = ""
    if not isinstance(target, str):
        diagnostics.append(f"E721: units[{index}].target must be a string")
        target = ""
    is_all = bool(item.get("all", False))
    suite_file = (
        resolve_path(
            item.get("suite_file"),
            base_dir=task_dir,
            diagnostics=diagnostics,
            field=f"units[{index}].suite_file",
        )
        if "suite_file" in item
        else None
    )
    if is_all and not target.strip():
        diagnostics.append(f"E721: units[{index}] with all=true requires target")
    if is_all and suite_file is not None:
        diagnostics.append(f"E721: units[{index}] cannot combine all=true with suite_file")
    if not is_all and suite_file is None:
        diagnostics.append(f"E721: units[{index}] requires suite_file or target with all=true")
    case_ids = item.get("case_ids", [])
    if case_ids is None:
        case_ids = []
    if not isinstance(case_ids, list) or not all(isinstance(case_id, str) for case_id in case_ids):
        diagnostics.append(f"E721: units[{index}].case_ids must be a list of strings")
        case_ids = []
    include_manual = _optional_bool(item.get("include_manual"), f"units[{index}].include_manual", diagnostics)
    return TaskUnit(
        target=target.strip(),
        name=str(item.get("name", "") or ""),
        module=str(item.get("module", "") or ""),
        suite=str(item.get("suite", "") or ""),
        suite_file=suite_file,
        case_ids=list(case_ids),
        include_manual=include_manual,
        pytest_args=_string_list(item.get("pytest_args", []), f"units[{index}].pytest_args", diagnostics),
        allow_risk=_string_list(item.get("allow_risk", []), f"units[{index}].allow_risk", diagnostics),
        all=is_all,
    )


def _task_defaults(value: Any, diagnostics: list[str]) -> TaskDefaults:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        diagnostics.append("E720: task defaults must be a mapping")
        value = {}
    return TaskDefaults(
        include_manual=_optional_bool(value.get("include_manual"), "defaults.include_manual", diagnostics),
        pytest_args=_string_list(value.get("pytest_args", []), "defaults.pytest_args", diagnostics),
        allow_risk=_string_list(value.get("allow_risk", []), "defaults.allow_risk", diagnostics),
    )


def _optional_bool(value: Any, field: str, diagnostics: list[str]) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        diagnostics.append(f"E721: {field} must be a boolean")
        return None
    return value


def _string_list(value: Any, field: str, diagnostics: list[str]) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        diagnostics.append(f"E721: {field} must be a list of strings")
        return []
    return list(value)


def _resolve_path_list(
    value: Any,
    *,
    base_dir: Path,
    diagnostics: list[str],
    field: str,
) -> list[Path]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        diagnostics.append(f"E700: {field} must be a list")
        return []
    paths: list[Path] = []
    for index, item in enumerate(value):
        path = resolve_path(item, base_dir=base_dir, diagnostics=diagnostics, field=f"{field}[{index}]")
        if path is not None:
            paths.append(path)
    return paths
