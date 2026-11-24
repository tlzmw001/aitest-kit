"""Emit a request scope around only the calls selected for log assertions."""
from dataclasses import asdict

from aitest_kit.codegen.render_utils import dict_to_python_compact
from aitest_kit.codegen.ir import SourcedLogAssertionGroupIR


def render_log_source_guard(flow):
    if not any(isinstance(group, SourcedLogAssertionGroupIR)
               for groups in flow.log_assertions.values() for group in groups):
        return []
    return [
        "        from aitest_kit.log_assertions import scope as __aitest_log_runtime",
        "        if not __aitest_log_runtime.__dict__.get('supports_multiple_log_sources', lambda: False)():",
        "            raise __aitest_log_runtime.LogBindingError('current executor does not support grouped log sources')",
    ]


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
