"""Load module-level codegen profile settings."""
from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

from aitest_kit.codegen.project_config import AssertionRule


@dataclass(frozen=True)
class RuntimeProfile:
    """Merged profile data used by planner/emitter at generation time."""

    data: dict[str, Any]
    module_profile_path: Path | None = None
    suite_profile_path: Path | None = None
    diagnostics: list[str] = field(default_factory=list)


ProfileSource = Optional[Union[str, Path, RuntimeProfile]]


@dataclass(frozen=True)
class CaseFlowDefaults:
    """Top-level defaults shared by profile case_flows."""

    fixture: str = ""
    object_name: str = ""
    case_setup: dict[str, Any] = field(default_factory=dict)


def preferred_module_profile_path(profile_dir: str | Path, module: str) -> Path:
    """Return the canonical module profile path."""
    return Path(profile_dir) / f"profile_{module}.md"


def resolve_module_profile_path(profile_dir: str | Path, module: str) -> Path | None:
    """Return the canonical module profile path when it exists."""
    preferred = preferred_module_profile_path(profile_dir, module)
    return preferred if preferred.exists() else None


def load_profile_yaml(profile_path: ProfileSource) -> dict[str, Any]:
    """Extract the first YAML block from a codegen_profile."""
    if profile_path is None:
        return {}
    if isinstance(profile_path, RuntimeProfile):
        return dict(profile_path.data)

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


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


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
            merged[key] = module_data[key]

    for key in ("default_fixture", "default_object", "default_case_setup"):
        if key in suite_data:
            merged[key] = suite_data[key]
        elif key in module_data:
            merged[key] = module_data[key]

    imports = []
    for raw in (module_data.get("extra_imports", []), suite_data.get("extra_imports", [])):
        if isinstance(raw, list):
            imports.extend(item for item in raw if isinstance(item, str) and item.strip())
    if imports:
        merged["extra_imports"] = _dedupe_strings(imports)

    for key in ("request_overrides", "case_fixtures", "case_bodies", "case_flows"):
        module_values = module_data.get(key, {})
        suite_values = suite_data.get(key, {})
        module_map = module_values if isinstance(module_values, dict) else {}
        suite_map = suite_values if isinstance(suite_values, dict) else {}
        overlap = sorted(set(module_map) & set(suite_map))
        if overlap:
            diagnostics.append(
                f"E520: profile merge conflict in {key}: " + ", ".join(overlap)
            )
        merged_values = {**module_map, **suite_map}
        if merged_values:
            merged[key] = merged_values

    variables = _merge_profile_variables(
        module_data.get("variables", {}),
        suite_data.get("variables", {}),
    )
    if variables:
        merged["variables"] = variables

    return merged, diagnostics


def _merge_profile_variables(
    module_variables: Any,
    suite_variables: Any,
) -> dict[str, Any]:
    module_map = module_variables if isinstance(module_variables, dict) else {}
    suite_map = suite_variables if isinstance(suite_variables, dict) else {}

    defaults = {
        **dict(module_map.get("defaults", {}) if isinstance(module_map.get("defaults"), dict) else {}),
        **dict(suite_map.get("defaults", {}) if isinstance(suite_map.get("defaults"), dict) else {}),
    }
    module_cases = module_map.get("cases", {}) if isinstance(module_map.get("cases"), dict) else {}
    suite_cases = suite_map.get("cases", {}) if isinstance(suite_map.get("cases"), dict) else {}
    cases: dict[str, Any] = {}
    for case_id in sorted(set(module_cases) | set(suite_cases)):
        module_case = module_cases.get(case_id, {}) if isinstance(module_cases.get(case_id), dict) else {}
        suite_case = suite_cases.get(case_id, {}) if isinstance(suite_cases.get(case_id), dict) else {}
        merged_case = {**module_case, **suite_case}
        if merged_case:
            cases[case_id] = merged_case

    result: dict[str, Any] = {}
    if defaults:
        result["defaults"] = defaults
    if cases:
        result["cases"] = cases
    return result


def load_profile_rules(profile_path: ProfileSource) -> list[AssertionRule]:
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


def load_profile_request_overrides(profile_path: ProfileSource) -> dict[str, dict[str, Any]]:
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


def load_profile_extra_imports(profile_path: ProfileSource) -> list[str]:
    """Extract extra import lines from a profile YAML block."""
    data = load_profile_yaml(profile_path)
    raw = data.get("extra_imports", [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str) and item.strip()]


def load_profile_case_fixtures(profile_path: ProfileSource) -> dict[str, list[str]]:
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


def load_profile_case_bodies(profile_path: ProfileSource) -> dict[str, list[str]]:
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


def load_profile_module_type(profile_path: ProfileSource) -> str | None:
    """Extract optional module_type from a profile YAML block."""
    data = load_profile_yaml(profile_path)
    module_type = data.get("module_type")
    return module_type if isinstance(module_type, str) and module_type.strip() else None


def load_profile_case_flow_defaults(profile_path: ProfileSource) -> CaseFlowDefaults:
    """Extract top-level case_flow defaults from a profile YAML block."""
    return case_flow_defaults_from_yaml(load_profile_yaml(profile_path))


def case_flow_defaults_from_yaml(data: dict[str, Any]) -> CaseFlowDefaults:
    """Build case_flow defaults from raw profile YAML data."""
    default_fixture = data.get("default_fixture")
    default_object = data.get("default_object")
    default_case_setup = data.get("default_case_setup")
    return CaseFlowDefaults(
        fixture=default_fixture if isinstance(default_fixture, str) else "",
        object_name=default_object if isinstance(default_object, str) else "",
        case_setup=dict(default_case_setup) if isinstance(default_case_setup, dict) else {},
    )


_CASE_ID_RE = re.compile(r"^TC-[A-Z0-9]+-\d+$")
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CALL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
_BACKTICK_RE = re.compile(r"`([^`]+)`")


def load_profile_case_flows(profile_path: ProfileSource) -> dict[str, dict[str, Any]]:
    """Extract structured case_flows from a profile YAML block."""
    data = load_profile_yaml(profile_path)
    raw = data.get("case_flows", {})
    case_flows = raw if isinstance(raw, dict) else {}
    return apply_case_flow_defaults(case_flows, case_flow_defaults_from_yaml(data))


class _SafeFormatDict(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _format_default_value(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return value.format_map(_SafeFormatDict(context))
    if isinstance(value, list):
        return [_format_default_value(item, context) for item in value]
    if isinstance(value, dict):
        return {
            key: _format_default_value(item, context)
            for key, item in value.items()
        }
    return value


def _default_setup_for_case(
    default_case_setup: dict[str, Any],
    case_id: str,
) -> dict[str, Any]:
    if not default_case_setup:
        return {}
    return _format_default_value(deepcopy(default_case_setup), {"case_id": case_id})


def _steps_start_with_default(
    steps: Any,
    default_step: dict[str, Any],
) -> bool:
    return isinstance(steps, list) and bool(steps) and steps[0] == default_step


def apply_case_flow_defaults(
    case_flows: dict[str, Any],
    defaults: CaseFlowDefaults | None = None,
) -> dict[str, dict[str, Any]]:
    """Return case_flows with top-level fixture/object/setup defaults applied."""
    defaults = defaults or CaseFlowDefaults()
    result: dict[str, dict[str, Any]] = {}
    for case_id, raw_flow in case_flows.items():
        if not isinstance(case_id, str) or not isinstance(raw_flow, dict):
            result[case_id] = raw_flow
            continue
        flow = deepcopy(raw_flow)
        if defaults.fixture and not flow.get("fixture"):
            flow["fixture"] = defaults.fixture
        if defaults.object_name and not flow.get("object"):
            flow["object"] = defaults.object_name

        default_step = _default_setup_for_case(defaults.case_setup, case_id)
        if default_step:
            steps = flow.get("steps", [])
            if not _steps_start_with_default(steps, default_step):
                flow["steps"] = [default_step, *list(steps if isinstance(steps, list) else [])]
        result[case_id] = flow
    return result


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


def validate_case_flows(
    case_flows: dict[str, Any],
    defaults: CaseFlowDefaults | None = None,
) -> list[str]:
    """Validate structured case_flow profile data without external deps."""
    errors: list[str] = []
    normalized = apply_case_flow_defaults(case_flows, defaults)
    for case_id, flow in normalized.items():
        prefix = f"case_flows.{case_id}"
        if not isinstance(case_id, str) or not _CASE_ID_RE.match(case_id):
            errors.append(f"{prefix}: invalid case_id")
            continue
        if not isinstance(flow, dict):
            errors.append(f"{prefix}: flow must be a mapping")
            continue

        allowed_flow_keys = {"fixture", "object", "description", "steps"}
        for key in flow:
            if key not in allowed_flow_keys:
                errors.append(f"{prefix}: unknown field {key}")

        description = flow.get("description")
        if description is not None and not isinstance(description, str):
            errors.append(f"{prefix}.description: must be a string")

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
        if set(value) == {"var"}:
            var_name = value["var"]
            if not isinstance(var_name, str) or not _IDENT_RE.match(var_name):
                errors.append(f"{prefix}.var: must be a valid profile variable name")
            return
        for key, item in value.items():
            _validate_case_flow_values(item, f"{prefix}.{key}", saved_names, errors)


def _case_flow_assert_text(assertion: str) -> str:
    return _BACKTICK_RE.sub(r"\1", assertion).strip()
