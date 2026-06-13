"""Rendering helpers for structured case_flow steps."""
from __future__ import annotations

from typing import Any

from aitest_kit.codegen.render_utils import dict_to_python_compact


def request_var_name(case_id: str) -> str:
    return "__request_" + case_id.lower().replace("-", "_")


def render_flow_value(
    value: Any,
    *,
    current_case_id: str,
    request_vars: dict[str, str],
) -> str:
    if isinstance(value, dict):
        keys = set(value)
        if keys == {"request_ref"}:
            ref = value["request_ref"]
            ref_case_id = current_case_id if ref == "self" else str(ref)
            return request_vars.get(ref_case_id, request_var_name(ref_case_id))
        if keys == {"ref"}:
            return str(value["ref"])
        if keys == {"expr"}:
            return str(value["expr"])
        if keys == {"var"}:
            return f"__tc_vars__[{dict_to_python_compact(value['var'])}]"
        pairs = [
            f"{dict_to_python_compact(key)}: "
            f"{render_flow_value(item, current_case_id=current_case_id, request_vars=request_vars)}"
            for key, item in value.items()
        ]
        return "{" + ", ".join(pairs) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(
            render_flow_value(item, current_case_id=current_case_id, request_vars=request_vars)
            for item in value
        ) + "]"
    return dict_to_python_compact(value)


def render_flow_call(
    step: Any,
    *,
    current_case_id: str,
    request_vars: dict[str, str],
) -> str:
    args = [
        render_flow_value(item, current_case_id=current_case_id, request_vars=request_vars)
        for item in step.args
    ]
    kwargs = [
        f"{key}={render_flow_value(value, current_case_id=current_case_id, request_vars=request_vars)}"
        for key, value in step.kwargs.items()
    ]
    params = ", ".join([*args, *kwargs])
    call = f"{step.call}({params})"
    return f"{step.save_as} = {call}" if step.save_as else call
