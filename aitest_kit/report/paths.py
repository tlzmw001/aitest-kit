"""Semantic report bucket paths for AITest run/report commands."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable


def suite_report_bucket(
    reports_root: str | Path,
    *,
    target: str,
    module: str,
    suite: str,
    case_ids: Iterable[str] = (),
) -> Path:
    """Return the report bucket for a direct suite run."""
    clean_case_ids = _clean_case_ids(case_ids)
    if clean_case_ids:
        return case_report_bucket(
            reports_root,
            target=target,
            module=module,
            case_ids=clean_case_ids,
        )
    return (
        Path(reports_root)
        / _safe_name(target)
        / _safe_name(module)
        / "suites"
        / _safe_name(suite)
    )


def selector_report_bucket(
    reports_root: str | Path,
    *,
    target: str = "",
    module: str = "",
    all_suites: bool = False,
    case_ids: Iterable[str] = (),
) -> Path:
    """Return the aggregate report bucket for target/module/all selectors."""
    clean_case_ids = _clean_case_ids(case_ids)
    root = Path(reports_root)
    if module:
        target_name = _safe_name(target) if target else "workspace"
        if clean_case_ids:
            return case_report_bucket(
                root,
                target=target_name,
                module=module,
                case_ids=clean_case_ids,
            )
        return root / target_name / _safe_name(module) / "module"
    if target:
        if clean_case_ids:
            return root / _safe_name(target) / "cases" / case_key(clean_case_ids)
        return root / _safe_name(target) / "target"
    if all_suites:
        if clean_case_ids:
            return root / "all" / "cases" / case_key(clean_case_ids)
        return root / "all"
    return root / "selected"


def task_report_bucket(reports_root: str | Path, task_name: str) -> Path:
    """Return the report bucket for an explicit task manifest."""
    return Path(reports_root) / "tasks" / _safe_name(task_name)


def case_report_bucket(
    reports_root: str | Path,
    *,
    target: str,
    module: str,
    case_ids: Iterable[str],
) -> Path:
    """Return the module-level case report bucket."""
    return Path(reports_root) / _safe_name(target) / _safe_name(module) / "cases" / case_key(case_ids)


def unit_report_dir(parent_run_dir: str | Path, unit_name: str) -> Path:
    """Return the unit report directory inside one aggregate run directory."""
    return Path(parent_run_dir) / "units" / _safe_name(unit_name)


def case_key(case_ids: Iterable[str]) -> str:
    """Return the deterministic directory key for one or more case ids."""
    clean = _clean_case_ids(case_ids)
    return "_".join(_safe_name(case_id.lower().replace("-", "_")) for case_id in clean) or "selected"


def _clean_case_ids(case_ids: Iterable[str]) -> list[str]:
    return [case_id.strip() for case_id in case_ids if isinstance(case_id, str) and case_id.strip()]


def _safe_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(value))
    return cleaned.strip("_") or "selected"

