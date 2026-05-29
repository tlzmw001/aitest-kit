"""Collect structured test results from generated pytest files and JUnit XML."""
from __future__ import annotations

import ast
import hashlib
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from aitest_kit.report.classifier import classify_failure
from aitest_kit.report.sanitizer import sanitize_message, traceback_summary


def project_config_version(path: str | Path = "aitest_config/aitest.yaml") -> str:
    config_path = Path(path)
    if not config_path.exists():
        return "missing"
    digest = hashlib.sha256(config_path.read_bytes()).hexdigest()
    return digest[:8]


def collect_result(
    *,
    junit_path: str | Path | None,
    generated_files: list[str | Path],
    run_id: str,
    command: str,
    timestamp: str | None = None,
    duration_seconds: float = 0.0,
    manual_policy: str = "excluded",
    codegen_check: dict[str, str] | None = None,
    environment: dict[str, Any] | None = None,
    status: str = "COMPLETED",
    run_scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the Phase 3 result.json payload."""
    files = [Path(p) for p in generated_files]
    meta = _extract_generated_metadata(files)
    cases = _parse_junit(Path(junit_path), meta) if junit_path else []

    manual_total = sum(1 for item in meta["by_full_key"].values() if item["is_manual"])
    manual_executed = sum(1 for item in cases if item.get("is_manual"))
    codegen_skipped_cases = list(meta["codegen_skipped"])

    summary = _summary(cases)
    summary.update({
        "auto_collected": len(cases),
        "manual_total": manual_total,
        "manual_executed": manual_executed,
        "manual_not_run": max(0, manual_total - manual_executed),
        "codegen_skipped": len(codegen_skipped_cases),
        "duration_seconds": duration_seconds,
    })

    result = {
        "run_id": run_id,
        "status": status,
        "timestamp": timestamp or datetime.now().astimezone().isoformat(timespec="seconds"),
        "duration_seconds": duration_seconds,
        "command": command,
        "project_config_version": project_config_version(),
        "manual_policy": manual_policy,
        "environment": environment or {},
        "codegen_check": codegen_check or {"status": "skipped", "command": "", "message": ""},
        "summary": summary,
        "modules": _module_summary(cases, codegen_skipped_cases, list(meta["by_full_key"].values())),
        "cases": cases,
        "codegen_skipped_cases": codegen_skipped_cases,
    }
    result.update(_run_scope_fields(run_scope))
    return result


def blocked_result(
    *,
    run_id: str,
    command: str,
    codegen_check: dict[str, str],
    generated_files: list[str | Path] | None = None,
    manual_policy: str = "excluded",
    blocked_reason: str = "codegen_check",
    environment: dict[str, Any] | None = None,
    run_scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = collect_result(
        junit_path=None,
        generated_files=[Path(p) for p in (generated_files or [])],
        run_id=run_id,
        command=command,
        manual_policy=manual_policy,
        codegen_check=codegen_check,
        environment=environment,
        status="BLOCKED_RUN",
        run_scope=run_scope,
    )
    result["blocked_reason"] = blocked_reason
    return result


def _run_scope_fields(run_scope: dict[str, Any] | None) -> dict[str, Any]:
    if not run_scope:
        return {}
    normalized = dict(run_scope)
    fields: dict[str, Any] = {"run_scope": normalized}
    for key in ("target", "module", "suite", "suite_file", "suite_dir", "task_file", "task"):
        if key in normalized:
            fields[key] = str(normalized.get(key) or "")
    if "case_files" in normalized:
        fields["case_files"] = [str(item) for item in normalized.get("case_files") or []]
    return fields


def _extract_generated_metadata(files: list[Path]) -> dict[str, Any]:
    by_full_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    class_func_candidates: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    codegen_skipped: list[dict[str, Any]] = []

    for path in files:
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for skipped in _module_skipped(tree):
            skipped = dict(skipped)
            skipped["suite"] = skipped.get("suite") or _suite_from_source(
                skipped.get("source") or skipped.get("source_md", "")
            )
            codegen_skipped.append(skipped)
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if not isinstance(item, ast.FunctionDef):
                    continue
                meta = _function_meta(item)
                if not meta:
                    continue
                meta = dict(meta)
                meta["suite"] = meta.get("suite") or _suite_from_source(
                    meta.get("source") or meta.get("source_md", "")
                )
                is_manual = _is_manual(item) or _meta_has_manual(meta)
                meta["is_manual"] = is_manual
                meta["nodeid"] = f"{path.as_posix()}::{node.name}::{item.name}"
                meta["file_path"] = path.as_posix()
                meta["class_name"] = node.name
                meta["function_name"] = item.name
                full_key = (path.as_posix(), node.name, item.name)
                by_full_key[full_key] = meta
                class_func_candidates[(node.name, item.name)].append(meta)

    by_class_func = {
        key: values[0]
        for key, values in class_func_candidates.items()
        if len(values) == 1
    }
    return {
        "by_full_key": by_full_key,
        "by_class_func": by_class_func,
        "codegen_skipped": codegen_skipped,
    }


def _function_meta(func: ast.FunctionDef) -> dict[str, Any] | None:
    for stmt in func.body:
        if not isinstance(stmt, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "__tc_meta__" for t in stmt.targets):
            continue
        try:
            value = ast.literal_eval(stmt.value)
        except (ValueError, SyntaxError):
            return None
        return value if isinstance(value, dict) else None
    return None


def _module_skipped(tree: ast.Module) -> list[dict[str, Any]]:
    for stmt in tree.body:
        if not isinstance(stmt, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "__codegen_skipped__" for t in stmt.targets):
            continue
        try:
            value = ast.literal_eval(stmt.value)
        except (ValueError, SyntaxError):
            return []
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _is_manual(func: ast.FunctionDef) -> bool:
    for deco in func.decorator_list:
        text = ast.unparse(deco) if hasattr(ast, "unparse") else ""
        if "pytest.mark.manual" in text or text.endswith(".manual"):
            return True
    return False


def _meta_has_manual(meta: dict[str, Any]) -> bool:
    return any("manual" in str(marker).lower() for marker in meta.get("markers", []))


def _parse_junit(junit_path: Path, meta: dict[str, Any]) -> list[dict[str, Any]]:
    if not junit_path.exists():
        return []
    root = ET.parse(junit_path).getroot()
    cases: list[dict[str, Any]] = []
    for testcase in root.iter():
        if _strip_ns(testcase.tag) != "testcase":
            continue
        case = _case_from_testcase(testcase, meta)
        cases.append(case)
    return cases


def _case_from_testcase(testcase: ET.Element, meta: dict[str, Any]) -> dict[str, Any]:
    name = testcase.attrib.get("name", "")
    func_name = name.split("[", 1)[0]
    classname = testcase.attrib.get("classname", "")
    class_name = classname.rsplit(".", 1)[-1] if classname else ""
    file_attr = testcase.attrib.get("file", "")

    matched = None
    if file_attr:
        full_key = (Path(file_attr).as_posix(), class_name, func_name)
        matched = meta["by_full_key"].get(full_key)
    if matched is None:
        matched = meta["by_class_func"].get((class_name, func_name))

    meta_source = "tc_meta" if matched else "unknown"
    if matched is None:
        matched = _fallback_meta(classname, func_name)
        meta_source = "nodeid_fallback" if matched.get("tc_id") != "UNKNOWN" else "unknown"

    outcome, failure = _outcome_and_failure(testcase)
    nodeid = matched.get("nodeid") or _fallback_nodeid(classname, func_name)
    result = {
        "nodeid": nodeid,
        "tc_id": matched.get("tc_id", "UNKNOWN"),
        "module": matched.get("module", "UNKNOWN"),
        "suite": matched.get("suite") or _suite_from_source(matched.get("source", "")),
        "category": matched.get("category", "UNKNOWN"),
        "source_md": matched.get("source") or matched.get("source_md", ""),
        "meta_source": meta_source,
        "title": matched.get("title", ""),
        "priority": matched.get("priority", ""),
        "markers": matched.get("markers", []),
        "is_manual": bool(matched.get("is_manual")),
        "outcome": outcome,
        "duration_seconds": float(testcase.attrib.get("time", "0") or 0),
    }
    if failure:
        result["failure"] = failure
    return result


def _outcome_and_failure(testcase: ET.Element) -> tuple[str, dict[str, Any] | None]:
    for child in testcase:
        tag = _strip_ns(child.tag)
        if tag == "skipped":
            return "pytest_skipped", None
        if tag in {"failure", "error"}:
            exception_type = _exception_type(child)
            phase = _phase(child)
            text = child.text or child.attrib.get("message", "")
            message = child.attrib.get("message") or text
            classification = classify_failure(phase, exception_type)
            failure = {
                "phase": phase,
                "classification": classification,
                "failure_type": classification,
                "exception_type": exception_type,
                "message": sanitize_message(message),
                "traceback_summary": traceback_summary(text, exception_type),
            }
            _attach_precondition_details(failure, message, text)
            return "failed" if tag == "failure" else "error", failure
    return "passed", None


def _attach_precondition_details(
    failure: dict[str, Any],
    message: str,
    text: str,
) -> None:
    if failure.get("classification") != "PRECONDITION_MISSING":
        return
    failure["blocker_type"] = "precondition_unmet"
    missing_env = sorted(set([
        *_extract_missing_env(message or ""),
        *_extract_missing_env(text or ""),
    ]))
    if missing_env:
        failure["missing_env"] = missing_env


def _extract_missing_env(text: str) -> list[str]:
    match = re.search(r"profile variable environment missing:\s*([^\r\n]+)", text)
    if not match:
        return []
    names: list[str] = []
    for item in match.group(1).split(","):
        env_name = item.strip().strip("`'\". ")
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", env_name):
            names.append(env_name)
    return sorted(set(names))


def _exception_type(node: ET.Element) -> str:
    type_attr = node.attrib.get("type", "")
    if type_attr:
        return type_attr.rsplit(".", 1)[-1]
    message = node.attrib.get("message", "") or node.text or ""
    match = re.search(r"([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception))", message)
    return match.group(1) if match else ("AssertionError" if _strip_ns(node.tag) == "failure" else "UnknownError")


def _phase(node: ET.Element) -> str:
    text = " ".join([node.attrib.get("message", ""), node.text or ""]).lower()
    if "teardown" in text:
        return "teardown"
    if "setup" in text:
        return "setup"
    return "call"


def _summary(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"passed": 0, "failed": 0, "error": 0, "pytest_skipped": 0}
    for case in cases:
        outcome = case.get("outcome")
        if outcome in counts:
            counts[outcome] += 1
    return counts


def _module_summary(
    cases: list[dict[str, Any]],
    skipped_cases: list[dict[str, Any]],
    all_meta: list[dict[str, Any]],
) -> dict[str, Any]:
    modules: dict[str, Any] = {}
    for item in all_meta:
        if item.get("is_manual"):
            bucket = _module_bucket(modules, item.get("module", "UNKNOWN"), item.get("category", "UNKNOWN"))
            bucket["manual_total"] += 1
    for case in cases:
        bucket = _module_bucket(modules, case.get("module", "UNKNOWN"), case.get("category", "UNKNOWN"))
        bucket["auto_collected"] += 1
        outcome = case.get("outcome")
        if outcome in {"passed", "failed", "error", "pytest_skipped"}:
            bucket[outcome] += 1
        if case.get("is_manual"):
            bucket["manual_executed"] += 1
    for skipped in skipped_cases:
        bucket = _module_bucket(modules, skipped.get("module", "UNKNOWN"), skipped.get("category", "UNKNOWN"))
        bucket["codegen_skipped"] += 1
    for categories in modules.values():
        for bucket in categories.values():
            bucket["manual_not_run"] = max(0, bucket["manual_total"] - bucket["manual_executed"])
    return modules


def _module_bucket(modules: dict[str, Any], module: str, category: str) -> dict[str, int]:
    categories = modules.setdefault(module or "UNKNOWN", {})
    return categories.setdefault(category or "UNKNOWN", {
        "auto_collected": 0,
        "passed": 0,
        "failed": 0,
        "error": 0,
        "pytest_skipped": 0,
        "manual_total": 0,
        "manual_executed": 0,
        "manual_not_run": 0,
        "codegen_skipped": 0,
    })


def _fallback_meta(classname: str, func_name: str) -> dict[str, Any]:
    module = "UNKNOWN"
    category = "UNKNOWN"
    match = re.search(r"test_(?P<module>.+)_(?P<category>business|boundary)", classname)
    if match:
        module = match.group("module")
        category = match.group("category")
    tc_id = _tc_id_from_func(func_name)
    return {
        "tc_id": tc_id,
        "module": module,
        "suite": "",
        "category": category,
        "source": "",
        "title": "",
        "priority": "",
        "markers": [],
        "is_manual": False,
        "nodeid": _fallback_nodeid(classname, func_name),
    }


def _tc_id_from_func(func_name: str) -> str:
    if not func_name.startswith("test_tc_"):
        return "UNKNOWN"
    parts = func_name[len("test_"):].split("_")
    if len(parts) < 3:
        return "UNKNOWN"
    return "-".join(part.upper() for part in parts)


def _suite_from_source(source: str) -> str:
    parts = Path(source).as_posix().split("/")
    try:
        index = parts.index("casesuites")
    except ValueError:
        return ""
    if index + 1 >= len(parts):
        return ""
    return parts[index + 1]


def _fallback_nodeid(classname: str, func_name: str) -> str:
    return f"{classname}::{func_name}" if classname else func_name


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
