from __future__ import annotations

import ast
import re
from pathlib import PurePosixPath
from typing import Any, Iterable

import yaml


EDITOR_CONTENT_LIMIT = 2 * 1024 * 1024

_PROFILE_KEYS = {
    "profile_scope",
    "parent_module",
    "parent_profile",
    "suite",
    "knowledge_refs",
    "assertion_rules",
    "structured_assertions",
    "variables",
    "requests",
    "extra_imports",
    "case_bodies",
    "case_flows",
}
_SUITE_FORBIDDEN_FIELDS = {
    "profile",
    "fixture",
    "fixtures",
    "helper",
    "helpers",
    "module_type",
    "case_flows",
    "case_bodies",
    "requests",
    "variables",
    "case_fixtures",
    "extra_imports",
    "assertion_rules",
    "structured_assertions",
    "default_fixture",
    "default_object",
    "default_case_setup",
    "case_ids",
    "include_manual",
    "pytest_args",
    "env_file",
    "allow_risk",
}
_FENCE_START = re.compile(r"^\s*```(?P<language>[A-Za-z0-9_-]*)\s*$")
_FENCE_END = re.compile(r"^\s*```\s*$")


def validate_editor_content(
    path: str,
    content: str,
    *,
    module_types: set[str],
) -> list[dict[str, Any]]:
    """Validate editor text without importing or executing workspace code."""
    normalized = PurePosixPath(path.replace("\\", "/"))
    suffix = normalized.suffix.lower()
    diagnostics: list[dict[str, Any]]
    if suffix in {".yaml", ".yml"}:
        diagnostics = _validate_yaml_document(normalized, content, module_types)
    elif suffix == ".py":
        diagnostics = _validate_python(content)
    elif suffix == ".md":
        diagnostics = _validate_markdown(normalized, content)
    else:
        diagnostics = []
    return sorted(diagnostics, key=_diagnostic_sort_key)


def _validate_yaml_document(
    path: PurePosixPath,
    content: str,
    module_types: set[str],
) -> list[dict[str, Any]]:
    data, diagnostics = _load_yaml(content, require_mapping=True)
    if diagnostics or data is None:
        return diagnostics

    name = path.name
    if name == "suite.yaml":
        diagnostics.extend(_required_fields(content, data, name, ("target", "module", "suite", "case_files")))
        if "case_files" in data and not isinstance(data["case_files"], list):
            diagnostics.append(_field_type(content, "case_files", "case_files 必须是列表"))
        for field in sorted(_SUITE_FORBIDDEN_FIELDS & set(data)):
            diagnostics.append(_field_error(
                content,
                field,
                "AITEST_FIELD_FORBIDDEN",
                f"suite.yaml 不允许字段：{field}",
            ))
    elif name == "target.yaml":
        diagnostics.extend(_required_fields(content, data, name, ("target",)))
    elif name == "module.yaml":
        diagnostics.extend(_required_fields(content, data, name, ("target", "module", "module_type")))
        module_type = data.get("module_type")
        if isinstance(module_type, str) and module_types and module_type not in module_types:
            diagnostics.append(_field_error(
                content,
                "module_type",
                "AITEST_MODULE_TYPE_UNKNOWN",
                f"module_type 未在 aitest.yaml 中声明：{module_type}",
            ))
        if "registered_suites" in data and not isinstance(data["registered_suites"], list):
            diagnostics.append(_field_type(content, "registered_suites", "registered_suites 必须是列表"))
    elif "tasks" in path.parts:
        diagnostics.extend(_required_fields(content, data, "task", ("schema_version", "name", "units")))
        if "units" in data and not isinstance(data["units"], list):
            diagnostics.append(_field_type(content, "units", "task units 必须是列表"))
    return diagnostics


def _validate_python(content: str) -> list[dict[str, Any]]:
    try:
        ast.parse(content)
    except SyntaxError as exc:
        line = max(1, exc.lineno or 1)
        column = max(1, exc.offset or 1)
        end_line = max(line, getattr(exc, "end_lineno", None) or line)
        end_column = max(column + 1, getattr(exc, "end_offset", None) or column + 1)
        return [_diagnostic(
            severity="error",
            code="PYTHON_SYNTAX",
            message=exc.msg,
            line=line,
            column=column,
            end_line=end_line,
            end_column=end_column,
            source="python",
        )]
    return []


def _validate_markdown(path: PurePosixPath, content: str) -> list[dict[str, Any]]:
    lines = content.splitlines()
    diagnostics: list[dict[str, Any]] = []
    index = 0
    is_profile = path.name == "profile.md" or (
        path.name.startswith("profile_") and path.name.endswith("_suite.md")
    )
    while index < len(lines):
        match = _FENCE_START.match(lines[index])
        if not match:
            index += 1
            continue
        closing = _find_fence_end(lines, index + 1)
        if closing is None:
            diagnostics.append(_diagnostic(
                severity="error",
                code="MARKDOWN_FENCE_UNCLOSED",
                message="Markdown fenced code block 未闭合",
                line=index + 1,
                column=1,
                source="markdown",
            ))
            break
        language = match.group("language").lower()
        if language in {"yaml", "yml"}:
            block = "\n".join(lines[index + 1:closing])
            data, yaml_diagnostics = _load_yaml(
                block,
                require_mapping=is_profile,
                line_offset=index + 1,
            )
            diagnostics.extend(yaml_diagnostics)
            if is_profile and isinstance(data, dict):
                for field in sorted(set(data) - _PROFILE_KEYS):
                    line, column = _find_key_location(block, field)
                    diagnostics.append(_diagnostic(
                        severity="warning",
                        code="PROFILE_FIELD_UNKNOWN",
                        message=f"Profile 包含未知顶层字段：{field}",
                        line=line + index + 1,
                        column=column,
                        source="aitest-profile",
                    ))
        index = closing + 1
    return diagnostics


def _load_yaml(
    content: str,
    *,
    require_mapping: bool,
    line_offset: int = 0,
) -> tuple[Any, list[dict[str, Any]]]:
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = (getattr(mark, "line", 0) or 0) + 1 + line_offset
        column = (getattr(mark, "column", 0) or 0) + 1
        message = getattr(exc, "problem", None) or "YAML 语法无效"
        return None, [_diagnostic(
            severity="error",
            code="YAML_SYNTAX",
            message=str(message),
            line=line,
            column=column,
            source="yaml",
        )]
    if data is None:
        data = {}
    if require_mapping and not isinstance(data, dict):
        return None, [_diagnostic(
            severity="error",
            code="YAML_ROOT_TYPE",
            message="AITest YAML 根节点必须是 mapping",
            line=1 + line_offset,
            column=1,
            source="yaml",
        )]
    return data, []


def _required_fields(
    content: str,
    data: dict[str, Any],
    label: str,
    fields: Iterable[str],
) -> list[dict[str, Any]]:
    return [
        _diagnostic(
            severity="error",
            code="AITEST_REQUIRED_FIELD",
            message=f"{label} 缺少必填字段：{field}",
            line=1,
            column=1,
            source="aitest-config",
        )
        for field in fields
        if field not in data
    ]


def _field_type(content: str, field: str, message: str) -> dict[str, Any]:
    return _field_error(content, field, "AITEST_FIELD_TYPE", message)


def _field_error(content: str, field: str, code: str, message: str) -> dict[str, Any]:
    line, column = _find_key_location(content, field)
    return _diagnostic(
        severity="error",
        code=code,
        message=message,
        line=line,
        column=column,
        end_column=column + len(field),
        source="aitest-config",
    )


def _find_key_location(content: str, field: str) -> tuple[int, int]:
    pattern = re.compile(rf"^(?P<indent>\s*){re.escape(field)}\s*:")
    for line_number, line in enumerate(content.splitlines(), start=1):
        match = pattern.match(line)
        if match:
            return line_number, len(match.group("indent")) + 1
    return 1, 1


def _find_fence_end(lines: list[str], start: int) -> int | None:
    for index in range(start, len(lines)):
        if _FENCE_END.match(lines[index]):
            return index
    return None


def _diagnostic(
    *,
    severity: str,
    code: str,
    message: str,
    line: int,
    column: int,
    source: str,
    end_line: int | None = None,
    end_column: int | None = None,
) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "line": max(1, line),
        "column": max(1, column),
        "end_line": max(1, end_line or line),
        "end_column": max(1, end_column or column + 1),
        "source": source,
    }


def _diagnostic_sort_key(item: dict[str, Any]) -> tuple[int, int, int, str]:
    severity = 0 if item["severity"] == "error" else 1
    return severity, item["line"], item["column"], item["code"]
