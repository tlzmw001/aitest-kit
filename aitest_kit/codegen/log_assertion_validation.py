"""Profile validation and normalization for deferred log assertions."""
from __future__ import annotations

import hashlib
import json
import keyword
from collections import Counter

from aitest_kit.log_assertions.rules import parse_check
from aitest_kit.log_assertions.values import expected_provider, freeze_expected, pointer_parts, sensitive_name


def iter_expected(flow):
    groups = flow.get("log_assertions")
    for group in groups if isinstance(groups, list) else ():
        expected = group.get("expected") if isinstance(group, dict) else None
        if isinstance(expected, dict):
            yield from expected.values()


def validate_log_assertions(flow, prefix):
    if "log_assertions" not in flow:
        return []
    groups = flow["log_assertions"]
    if not isinstance(groups, list) or not groups:
        return [("E533", f"{prefix}.log_assertions: expected a nonempty list")]
    errors = []
    names = set()
    calls = set()
    for step in flow.get("steps", []):
        if not isinstance(step, dict):
            continue
        for field in ("save_as", "assign"):
            name = step.get(field)
            if not isinstance(name, str) or not name:
                continue
            if name in {"__aitest_log_step", "__aitest_log_scope"}:
                errors.append(("E533", f"{prefix}: reserved step name {name}"))
            if name in names:
                errors.append(("E533", f"{prefix}: duplicate step name {name}"))
            names.add(name)
            if field == "save_as" and "call" in step:
                calls.add(name)
    counts = Counter()
    policies = {}
    literals = {}
    for index, group in enumerate(groups):
        path = f"{prefix}.log_assertions[{index}]"
        if not isinstance(group, dict) or set(group) - {"request_step", "select", "expected", "checks", "cleanup"}:
            errors.append(("E533", f"{path}: invalid group or unknown field"))
            continue
        request = group.get("request_step")
        if not isinstance(request, str) or request not in calls:
            errors.append(("E533", f"{path}.request_step: must name a call's save_as"))
            continue
        counts[request] += 1
        if counts[request] == 33:
            errors.append(("E533", f"{path}: more than 32 groups for this request"))
        select = group.get("select", {})
        if not isinstance(select, dict) or any(
            k not in {"eventType", "stage"} or not isinstance(v, str) or not v.strip()
            for k, v in select.items()
        ):
            errors.append(("E533", f"{path}.select: expected eventType/stage strings"))
        if "cleanup" in group:
            policy = group["cleanup"]
            if policy not in ("retain", "on_success") or policies.get(request, policy) != policy:
                errors.append(("E536", f"{path}.cleanup: invalid or conflicting policy"))
            else:
                policies[request] = policy
        checks = group.get("checks")
        if not isinstance(checks, list) or not 1 <= len(checks) <= 32:
            errors.append(("E534", f"{path}.checks: expected 1–32 checks"))
        else:
            for number, source in enumerate(checks):
                try:
                    parse_check(source)
                except ValueError as exc:
                    errors.append(("E534", f"{path}.checks[{number}]: {exc}"))
        expected = group.get("expected", {})
        if not isinstance(expected, dict):
            errors.append(("E535", f"{path}.expected: expected a mapping"))
            continue
        static = {}
        for key, value in expected.items():
            try:
                if not isinstance(key, str) or not key.isidentifier() or key.startswith("_") or keyword.iskeyword(key):
                    raise ValueError("invalid expected name")
                provider = expected_provider(value)
                if sensitive_name(key):
                    raise ValueError("sensitive expected fields cannot be frozen")
                if "from_response" in provider and any(
                    sensitive_name(part) for part in pointer_parts(provider["from_response"])
                ):
                    raise ValueError("sensitive response fields cannot be frozen")
                if "literal" in provider:
                    static[key] = provider["literal"]
            except ValueError as exc:
                errors.append(("E535", f"{path}.expected.{key}: {exc}"))
        literals.setdefault(request, []).append(static)
    for request, inputs in literals.items():
        try:
            freeze_expected(inputs)
        except ValueError as exc:
            errors.append(("E535", f"{prefix}.log_assertions ({request}): {exc}"))
    return errors


def build_log_groups(groups):
    from aitest_kit.codegen.ir import LogAssertionGroupIR

    policies = {group["request_step"]: group["cleanup"] for group in groups if "cleanup" in group}
    result = {}
    for index, group in enumerate(groups):
        step = group["request_step"]
        payload = {
            "request_step": step,
            "group_index": index,
            "select": group.get("select", {}),
            "expected": {key: expected_provider(value) for key, value in group.get("expected", {}).items()},
            "checks": group["checks"],
            "cleanup": policies.get(step, "retain"),
            "executor_version": 1,
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False)
        result.setdefault(step, []).append(LogAssertionGroupIR(
            **payload, rule_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        ))
    return result


def validate_expected_variables(flow, prefix, variables):
    from aitest_kit.codegen.profile_variables import variable_specs_for_case

    errors = []
    for index, group in enumerate(flow["log_assertions"]):
        if not isinstance(group, dict) or not isinstance(group.get("expected"), dict):
            continue
        for key, provider in group["expected"].items():
            if not isinstance(provider, dict) or set(provider) != {"from_var"}:
                continue
            name = provider["from_var"]
            if not isinstance(name, str):
                continue
            specs = variable_specs_for_case(variables, prefix.rsplit(".", 1)[-1], {name})
            spec = specs.get(name, {})
            path = f"{prefix}.log_assertions[{index}].expected.{key}"
            if not spec:
                errors.append(("E535", f"{path}: undefined profile variable {name}"))
            elif sensitive_name(name) or sensitive_name(str(spec.get("env", ""))):
                errors.append(("E535", f"{path}: sensitive profile variables cannot be frozen"))
    return errors


def validate_log_flow(flow, prefix, module_binding, variables):
    if not isinstance(flow, dict) or "log_assertions" not in flow:
        return []
    errors = []
    if not module_binding or not module_binding.log_capture:
        errors.append(("E536", f"{prefix}: module.yaml requires log_capture.source_id"))
    if isinstance(flow.get("steps"), list):
        errors.extend(validate_log_assertions(flow, prefix))
        if isinstance(flow["log_assertions"], list):
            errors.extend(validate_expected_variables(flow, prefix, variables))
    return errors
