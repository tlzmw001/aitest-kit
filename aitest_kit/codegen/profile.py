"""Load module-level codegen profile settings."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from aitest_kit.codegen.project_config import AssertionRule


def load_profile_yaml(profile_path: str | Path) -> dict[str, Any]:
    """Extract the first YAML block from a codegen_profile."""
    path = Path(profile_path)
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    m = re.search(r"```ya?ml\s*\n(.*?)```", text, re.DOTALL)
    if not m:
        return {}

    try:
        import yaml
        data = yaml.safe_load(m.group(1))
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def load_profile_rules(profile_path: str | Path) -> list[AssertionRule]:
    """Extract assertion_rules from a codegen_profile's YAML block."""
    data = load_profile_yaml(profile_path)
    if not data:
        return []

    rules: list[AssertionRule] = []
    for item in data.get("assertion_rules", []):
        if not isinstance(item, dict):
            continue
        rules.append(AssertionRule(
            pattern=item.get("pattern", "") or "",
            template=item.get("template", "") or "",
            regex=item.get("regex", "") or "",
            extract_vars=item.get("extract_vars", []) or [],
            params=item.get("params", {}) or {},
            name=item.get("name", "") or "",
        ))
    return rules


def load_profile_request_overrides(profile_path: str | Path) -> dict[str, dict[str, Any]]:
    """Extract explicit case-level request overrides from a profile YAML block."""
    data = load_profile_yaml(profile_path)
    raw = data.get("request_overrides", {})
    if not isinstance(raw, dict):
        return {}

    result: dict[str, dict[str, Any]] = {}
    for case_id, overrides in raw.items():
        if isinstance(case_id, str) and isinstance(overrides, dict):
            result[case_id] = dict(overrides)
    return result


def load_profile_extra_imports(profile_path: str | Path) -> list[str]:
    """Extract extra import lines from a profile YAML block."""
    data = load_profile_yaml(profile_path)
    raw = data.get("extra_imports", [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str) and item.strip()]


def load_profile_case_fixtures(profile_path: str | Path) -> dict[str, list[str]]:
    """Extract per-case fixture signatures from a profile YAML block."""
    data = load_profile_yaml(profile_path)
    raw = data.get("case_fixtures", {})
    if not isinstance(raw, dict):
        return {}

    result: dict[str, list[str]] = {}
    for case_id, fixtures in raw.items():
        if not isinstance(case_id, str) or not isinstance(fixtures, list):
            continue
        result[case_id] = [
            item for item in fixtures
            if isinstance(item, str) and item.strip()
        ]
    return result


def load_profile_case_bodies(profile_path: str | Path) -> dict[str, list[str]]:
    """Extract per-case test body lines from a profile YAML block."""
    data = load_profile_yaml(profile_path)
    raw = data.get("case_bodies", {})
    if not isinstance(raw, dict):
        return {}

    result: dict[str, list[str]] = {}
    for case_id, body in raw.items():
        if not isinstance(case_id, str):
            continue
        if isinstance(body, str):
            result[case_id] = body.splitlines()
        elif isinstance(body, list):
            result[case_id] = [
                item for item in body
                if isinstance(item, str)
            ]
    return result


def load_profile_module_type(profile_path: str | Path) -> str | None:
    """Extract optional module_type from a profile YAML block."""
    data = load_profile_yaml(profile_path)
    module_type = data.get("module_type")
    return module_type if isinstance(module_type, str) and module_type.strip() else None


_CASE_ID_RE = re.compile(r"^TC-[A-Z0-9]+-\d+$")
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CALL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
_BACKTICK_RE = re.compile(r"`([^`]+)`")


def load_profile_case_flows(profile_path: str | Path) -> dict[str, dict[str, Any]]:
    """Extract structured case_flows from a profile YAML block."""
    data = load_profile_yaml(profile_path)
    raw = data.get("case_flows", {})
    return raw if isinstance(raw, dict) else {}


def validate_profile_strategy_conflicts(
    case_bodies: dict[str, Any],
    case_flows: dict[str, Any],
) -> list[str]:
    """Reject ambiguous per-case generation strategies."""
    overlap = sorted(set(case_bodies) & set(case_flows))
    if not overlap:
        return []
    return [
        "profile case strategy conflict: the following cases are defined in both "
        f"case_bodies and case_flows: {', '.join(overlap)}"
    ]


def validate_case_flows(case_flows: dict[str, Any]) -> list[str]:
    """Validate structured case_flow profile data without external deps."""
    errors: list[str] = []
    for case_id, flow in case_flows.items():
        prefix = f"case_flows.{case_id}"
        if not isinstance(case_id, str) or not _CASE_ID_RE.match(case_id):
            errors.append(f"{prefix}: invalid case_id")
            continue
        if not isinstance(flow, dict):
            errors.append(f"{prefix}: flow must be a mapping")
            continue

        allowed_flow_keys = {"fixture", "object", "steps"}
        for key in flow:
            if key not in allowed_flow_keys:
                errors.append(f"{prefix}: unknown field {key}")

        fixture = flow.get("fixture")
        if not isinstance(fixture, str) or not fixture.strip():
            errors.append(f"{prefix}.fixture: must be a non-empty string")

        obj_name = flow.get("object")
        if obj_name is not None and (
            not isinstance(obj_name, str) or not _IDENT_RE.match(obj_name)
        ):
            errors.append(f"{prefix}.object: must be a valid Python identifier")

        steps = flow.get("steps")
        if not isinstance(steps, list) or not steps:
            errors.append(f"{prefix}.steps: must be a non-empty list")
            continue

        saved_names: set[str] = set()
        for index, step in enumerate(steps):
            step_prefix = f"{prefix}.steps[{index}]"
            _validate_case_flow_step(step, step_prefix, saved_names, errors)
    return errors


def _validate_case_flow_step(
    step: Any,
    prefix: str,
    saved_names: set[str],
    errors: list[str],
) -> None:
    if not isinstance(step, dict):
        errors.append(f"{prefix}: step must be a mapping")
        return

    has_call = "call" in step
    has_assert = "assert" in step
    has_assign = "assign" in step
    has_comment = "comment" in step
    mode_count = sum([has_call, has_assert, has_assign, has_comment])
    if mode_count != 1:
        errors.append(f"{prefix}: step must contain exactly one of call/assert/assign/comment")

    if has_call and mode_count == 1:
        allowed_keys = {"call", "args", "kwargs", "save_as"}
    elif has_assert and mode_count == 1:
        allowed_keys = {"assert"}
    elif has_assign and mode_count == 1:
        allowed_keys = {"assign", "expr"}
    elif has_comment and mode_count == 1:
        allowed_keys = {"comment"}
    else:
        allowed_keys = {"call", "assert", "assign", "comment", "args", "kwargs", "save_as", "expr"}
    for key in step:
        if key not in allowed_keys:
            errors.append(f"{prefix}: unknown field {key}")

    if has_call and (
        not isinstance(step.get("call"), str) or not _CALL_RE.match(step["call"])
    ):
        errors.append(f"{prefix}.call: must be a valid dotted call path")
    if has_assert:
        assertion = step.get("assert")
        if not isinstance(assertion, str):
            errors.append(f"{prefix}.assert: must be a string")
        elif not _case_flow_assert_text(assertion).startswith("assert "):
            errors.append(
                f"{prefix}.assert: must start with 'assert ' after optional backticks"
            )
    if has_assign:
        target = step.get("assign")
        if not isinstance(target, str) or not _IDENT_RE.match(target):
            errors.append(f"{prefix}.assign: must be a valid Python identifier")
        else:
            saved_names.add(target)
        expr = step.get("expr")
        if not isinstance(expr, str) or not expr.strip():
            errors.append(f"{prefix}.expr: must be a non-empty string")
    if has_comment and (
        not isinstance(step.get("comment"), str) or not step["comment"].strip()
    ):
        errors.append(f"{prefix}.comment: must be a non-empty string")

    args = step.get("args", [])
    if args is not None and not isinstance(args, list):
        errors.append(f"{prefix}.args: must be a list")
    kwargs = step.get("kwargs", {})
    if kwargs is not None and not isinstance(kwargs, dict):
        errors.append(f"{prefix}.kwargs: must be a mapping")
    if isinstance(kwargs, dict):
        for key in kwargs:
            if not isinstance(key, str) or not _IDENT_RE.match(key):
                errors.append(f"{prefix}.kwargs.{key}: key must be a valid Python identifier")

    _validate_case_flow_values(args, f"{prefix}.args", saved_names, errors)
    _validate_case_flow_values(kwargs, f"{prefix}.kwargs", saved_names, errors)

    save_as = step.get("save_as")
    if save_as is not None:
        if not isinstance(save_as, str) or not _IDENT_RE.match(save_as):
            errors.append(f"{prefix}.save_as: must be a valid Python identifier")
        else:
            saved_names.add(save_as)


def _validate_case_flow_values(
    value: Any,
    prefix: str,
    saved_names: set[str],
    errors: list[str],
) -> None:
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_case_flow_values(item, f"{prefix}[{index}]", saved_names, errors)
        return
    if isinstance(value, dict):
        if set(value) == {"ref"}:
            ref = value["ref"]
            if not isinstance(ref, str) or ref not in saved_names:
                errors.append(f"{prefix}.ref: must reference a previous save_as")
            return
        if set(value) == {"expr"}:
            if not isinstance(value["expr"], str) or not value["expr"].strip():
                errors.append(f"{prefix}.expr: must be a non-empty string")
            return
        for key, item in value.items():
            _validate_case_flow_values(item, f"{prefix}.{key}", saved_names, errors)


def _case_flow_assert_text(assertion: str) -> str:
    return _BACKTICK_RE.sub(r"\1", assertion).strip()
