"""Helpers for codegen profile variables."""
from __future__ import annotations

import re
from typing import Any

from aitest_kit.codegen.ir import ProfileVariableIR


_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_profile_variables(data: dict[str, Any]) -> dict[str, Any]:
    raw = data.get("variables", {})
    return raw if isinstance(raw, dict) else {}


def variable_specs_for_case(
    variables: dict[str, Any],
    case_id: str,
    refs: set[str],
) -> dict[str, dict[str, Any]]:
    defaults = variables.get("defaults", {}) if isinstance(variables.get("defaults"), dict) else {}
    cases = variables.get("cases", {}) if isinstance(variables.get("cases"), dict) else {}
    case_vars = cases.get(case_id, {}) if isinstance(cases.get(case_id), dict) else {}
    available = {**defaults, **case_vars}
    return {
        name: dict(available[name])
        for name in sorted(refs)
        if isinstance(available.get(name), dict)
    }


def profile_variable_irs_for_case(
    variables: dict[str, Any],
    case_id: str,
    refs: set[str],
) -> list[ProfileVariableIR]:
    specs = variable_specs_for_case(variables, case_id, refs)
    cases = variables.get("cases", {}) if isinstance(variables.get("cases"), dict) else {}
    case_vars = cases.get(case_id, {}) if isinstance(cases.get(case_id), dict) else {}
    result: list[ProfileVariableIR] = []

    for name, spec in specs.items():
        source = (
            f"profile.variables.cases.{case_id}.{name}"
            if name in case_vars
            else f"profile.variables.defaults.{name}"
        )
        if "env" in spec:
            result.append(ProfileVariableIR(
                name=name,
                provider="env",
                source=source,
                env=str(spec["env"]),
            ))
        elif "value" in spec:
            result.append(ProfileVariableIR(
                name=name,
                provider="value",
                source=source,
                value=spec.get("value"),
            ))
    return result


def case_flow_variable_refs(flow: Any) -> set[str]:
    refs: set[str] = set()
    if not isinstance(flow, dict):
        return refs
    steps = flow.get("steps", [])
    for step in steps if isinstance(steps, list) else []:
        if not isinstance(step, dict):
            continue
        if "call" in step:
            _collect_variable_refs(step.get("args", []), refs)
            _collect_variable_refs(step.get("kwargs", {}), refs)
    return refs


def validate_profile_variables(variables: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in variables:
        if key not in {"defaults", "cases"}:
            errors.append(f"variables: unknown field {key}")

    defaults = variables.get("defaults", {})
    if defaults is not None and not isinstance(defaults, dict):
        errors.append("variables.defaults: must be a mapping")
    elif isinstance(defaults, dict):
        _validate_variable_map(defaults, "variables.defaults", errors)

    cases = variables.get("cases", {})
    if cases is not None and not isinstance(cases, dict):
        errors.append("variables.cases: must be a mapping")
    elif isinstance(cases, dict):
        for case_id, case_vars in cases.items():
            prefix = f"variables.cases.{case_id}"
            if not isinstance(case_vars, dict):
                errors.append(f"{prefix}: must be a mapping")
                continue
            _validate_variable_map(case_vars, prefix, errors)

    return errors


def validate_case_flow_variable_references(
    case_flows: dict[str, Any],
    variables: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    defaults = variables.get("defaults", {}) if isinstance(variables.get("defaults"), dict) else {}
    cases = variables.get("cases", {}) if isinstance(variables.get("cases"), dict) else {}
    for case_id, flow in case_flows.items():
        refs = case_flow_variable_refs(flow)
        if not refs:
            continue
        case_vars = cases.get(case_id, {}) if isinstance(cases.get(case_id), dict) else {}
        missing = sorted(refs - (set(defaults) | set(case_vars)))
        if missing:
            errors.append(
                f"case_flows.{case_id}: undefined profile variables: " + ", ".join(missing)
            )
    return errors


def _collect_variable_refs(value: Any, refs: set[str]) -> None:
    if isinstance(value, list):
        for item in value:
            _collect_variable_refs(item, refs)
        return
    if isinstance(value, dict):
        if set(value) == {"var"} and isinstance(value["var"], str):
            refs.add(value["var"])
            return
        for item in value.values():
            _collect_variable_refs(item, refs)


def _validate_variable_map(value: dict[str, Any], prefix: str, errors: list[str]) -> None:
    for name, spec in value.items():
        item_prefix = f"{prefix}.{name}"
        if not isinstance(name, str) or not _IDENT_RE.match(name):
            errors.append(f"{item_prefix}: variable name must be a valid Python identifier")
        if not isinstance(spec, dict):
            errors.append(f"{item_prefix}: must be a mapping")
            continue
        keys = set(spec)
        if keys == {"env"}:
            if not isinstance(spec["env"], str) or not spec["env"].strip():
                errors.append(f"{item_prefix}.env: must be a non-empty string")
            continue
        if keys == {"value"}:
            continue
        errors.append(f"{item_prefix}: must declare exactly one of env or value")
