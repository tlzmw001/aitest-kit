"""Render structured profile structured assertions into deterministic Python."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from aitest_kit.codegen.render_utils import dict_to_python_compact


SUPPORTED_STRUCTURED_ASSERTION_TYPES = {
    "jsonpath_equals",
    "jsonpath_exists",
    "jsonpath_not_exists",
    "jsonpath_all_equals",
    "jsonpath_any_equals",
    "jsonpath_len_equals",
    "jsonpath_len_gte",
    "jsonpath_field_in_set",
}


def structured_assertion_required_fields(template_type: str) -> set[str]:
    """Return required fields for one supported structured assertion type."""
    base = {"type", "target", "path"}
    if template_type in {"jsonpath_equals", "jsonpath_all_equals", "jsonpath_any_equals"}:
        return base | {"equals"}
    if template_type in {"jsonpath_len_equals", "jsonpath_len_gte"}:
        return base | {"value"}
    if template_type == "jsonpath_field_in_set":
        return base | {"values"}
    return base


def render_structured_assertion(template: dict[str, Any]) -> list[str]:
    """Render one structured assertion as generated pytest code lines."""
    template_type = str(template.get("type", "") or "")
    target = str(template.get("target", "") or "")
    path = str(template.get("path", "") or "")

    if template_type == "jsonpath_equals":
        return [
            "aitest_assertions.assert_jsonpath_equals("
            f"{target}, {dict_to_python_compact(path)}, {dict_to_python_compact(template.get('equals'))})"
        ]
    if template_type == "jsonpath_exists":
        return [
            "aitest_assertions.assert_jsonpath_exists("
            f"{target}, {dict_to_python_compact(path)})"
        ]
    if template_type == "jsonpath_not_exists":
        return [
            "aitest_assertions.assert_jsonpath_not_exists("
            f"{target}, {dict_to_python_compact(path)})"
        ]
    if template_type == "jsonpath_all_equals":
        return [
            "aitest_assertions.assert_jsonpath_all_equals("
            f"{target}, {dict_to_python_compact(path)}, {dict_to_python_compact(template.get('equals'))})"
        ]
    if template_type == "jsonpath_any_equals":
        return [
            "aitest_assertions.assert_jsonpath_any_equals("
            f"{target}, {dict_to_python_compact(path)}, {dict_to_python_compact(template.get('equals'))})"
        ]
    if template_type == "jsonpath_len_equals":
        return [
            "aitest_assertions.assert_jsonpath_len_equals("
            f"{target}, {dict_to_python_compact(path)}, {dict_to_python_compact(template.get('value'))})"
        ]
    if template_type == "jsonpath_len_gte":
        return [
            "aitest_assertions.assert_jsonpath_len_gte("
            f"{target}, {dict_to_python_compact(path)}, {dict_to_python_compact(template.get('value'))})"
        ]
    if template_type == "jsonpath_field_in_set":
        return [
            "aitest_assertions.assert_jsonpath_field_in_set("
            f"{target}, {dict_to_python_compact(path)}, {dict_to_python_compact(template.get('values'))})"
        ]
    return [f"# UNKNOWN STRUCTURED ASSERTION: {template_type}"]


def structured_assertion_source(template: dict[str, Any]) -> str:
    """Return a compact human-readable source summary for IR dumps."""
    template_type = str(template.get("type", "") or "")
    target = str(template.get("target", "") or "")
    path = str(template.get("path", "") or "")
    if "equals" in template:
        return f"{template_type} {target} {path} == {template.get('equals')!r}"
    if "value" in template:
        return f"{template_type} {target} {path} value={template.get('value')!r}"
    if "values" in template:
        return f"{template_type} {target} {path} values={template.get('values')!r}"
    return f"{template_type} {target} {path}"


def structured_assertion_metadata(template: dict[str, Any]) -> dict[str, Any]:
    """Return stable metadata for structured assertion review surfaces."""
    result: dict[str, Any] = {
        "type": str(template.get("type", "") or ""),
        "target": str(template.get("target", "") or ""),
        "path": str(template.get("path", "") or ""),
    }
    for key in ("equals", "value", "values"):
        if key in template:
            result[key] = deepcopy(template[key])
    return result
