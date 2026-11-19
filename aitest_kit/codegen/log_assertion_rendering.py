"""Emit a request scope around only the calls selected for log assertions."""
from dataclasses import asdict

from aitest_kit.codegen.render_utils import dict_to_python_compact


def render_log_call(flow, step, call):
    groups = flow.log_assertions.get(step.save_as)
    if not groups:
        return [f"        {call}"]
    inputs = "__tc_vars__" if any(
        "from_var" in provider for group in groups for provider in group.expected.values()
    ) else "{}"
    rules = dict_to_python_compact([asdict(group) for group in groups])
    return [
        "        from aitest_kit.log_assertions.scope import log_request_step as __aitest_log_step",
        f"        with __aitest_log_step(request_step={step.save_as!r}, source_id={flow.log_source_id!r},",
        f"                               rules={rules}, expected_inputs={inputs}) as __aitest_log_scope:",
        f"            {call}",
        f"            __aitest_log_scope.freeze_response({step.save_as})",
    ]
