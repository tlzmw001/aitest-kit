"""Merge helpers for module and suite codegen profiles."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _deep_merge(base: Any, override: Any) -> Any:
    """Merge nested profile values, merging lists by index."""
    if isinstance(base, dict) and isinstance(override, dict):
        result = deepcopy(base)
        for key, value in override.items():
            if key in result:
                result[key] = _deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result

    if isinstance(base, list) and isinstance(override, list):
        result: list[Any] = []
        max_len = max(len(base), len(override))
        for index in range(max_len):
            has_base = index < len(base)
            has_override = index < len(override)
            if has_base and has_override:
                result.append(_deep_merge(base[index], override[index]))
            elif has_override:
                result.append(deepcopy(override[index]))
            else:
                result.append(deepcopy(base[index]))
        return result

    return deepcopy(override)


def merge_profile_yaml(
    module_data: dict[str, Any],
    suite_data: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Merge stable module profile data with optional case-suite profile data."""
    suite_data = suite_data or {}
    merged: dict[str, Any] = {}
    diagnostics: list[str] = []

    for key in ("module_type", "assertion_rules"):
        if key in module_data:
            merged[key] = deepcopy(module_data[key])

    for key in ("default_fixture", "default_object"):
        if key in suite_data:
            merged[key] = deepcopy(suite_data[key])
        elif key in module_data:
            merged[key] = deepcopy(module_data[key])

    if "default_case_setup" in suite_data and "default_case_setup" in module_data:
        merged["default_case_setup"] = _deep_merge(
            module_data["default_case_setup"],
            suite_data["default_case_setup"],
        )
    elif "default_case_setup" in suite_data:
        merged["default_case_setup"] = deepcopy(suite_data["default_case_setup"])
    elif "default_case_setup" in module_data:
        merged["default_case_setup"] = deepcopy(module_data["default_case_setup"])

    imports = []
    for raw in (module_data.get("extra_imports", []), suite_data.get("extra_imports", [])):
        if isinstance(raw, list):
            imports.extend(item for item in raw if isinstance(item, str) and item.strip())
    if imports:
        merged["extra_imports"] = _dedupe_strings(imports)

    for key in ("request_overrides", "case_flows"):
        module_values = module_data.get(key, {})
        suite_values = suite_data.get(key, {})
        module_map = module_values if isinstance(module_values, dict) else {}
        suite_map = suite_values if isinstance(suite_values, dict) else {}
        merged_values = _merge_case_maps(module_map, suite_map)
        if merged_values:
            merged[key] = merged_values

    for key in ("case_fixtures", "case_bodies"):
        module_values = module_data.get(key, {})
        suite_values = suite_data.get(key, {})
        module_map = module_values if isinstance(module_values, dict) else {}
        suite_map = suite_values if isinstance(suite_values, dict) else {}
        overlap = sorted(set(module_map) & set(suite_map))
        if overlap:
            diagnostics.append(
                f"E520: profile merge conflict in {key}: " + ", ".join(overlap)
            )
        merged_values = {**deepcopy(module_map), **deepcopy(suite_map)}
        if merged_values:
            merged[key] = merged_values

    variables = _merge_profile_variables(
        module_data.get("variables", {}),
        suite_data.get("variables", {}),
    )
    if variables:
        merged["variables"] = variables

    return merged, diagnostics


def _merge_case_maps(module_map: dict[str, Any], suite_map: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for case_id in sorted(set(module_map) | set(suite_map)):
        has_module = case_id in module_map
        has_suite = case_id in suite_map
        if has_module and has_suite:
            result[case_id] = _deep_merge(module_map[case_id], suite_map[case_id])
        elif has_suite:
            result[case_id] = deepcopy(suite_map[case_id])
        else:
            result[case_id] = deepcopy(module_map[case_id])
    return result


def _merge_profile_variables(
    module_variables: Any,
    suite_variables: Any,
) -> dict[str, Any]:
    module_map = module_variables if isinstance(module_variables, dict) else {}
    suite_map = suite_variables if isinstance(suite_variables, dict) else {}

    defaults = _deep_merge(
        module_map.get("defaults", {}) if isinstance(module_map.get("defaults"), dict) else {},
        suite_map.get("defaults", {}) if isinstance(suite_map.get("defaults"), dict) else {},
    )
    module_cases = module_map.get("cases", {}) if isinstance(module_map.get("cases"), dict) else {}
    suite_cases = suite_map.get("cases", {}) if isinstance(suite_map.get("cases"), dict) else {}
    cases = _merge_case_maps(module_cases, suite_cases)

    result: dict[str, Any] = {}
    if defaults:
        result["defaults"] = defaults
    if cases:
        result["cases"] = cases
    return result
