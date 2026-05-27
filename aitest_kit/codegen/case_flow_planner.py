"""Build structured case_flow IR from profile data."""
from __future__ import annotations

from typing import Any

from aitest_kit.codegen.ir import AssertionIR, CaseFlowIR, CaseFlowStepIR
from aitest_kit.codegen.parser import TestCase
from aitest_kit.codegen.project_config import AssertionRule, ProjectConfig
from aitest_kit.codegen.render_utils import resolve_assertion, strip_backticks


def build_case_flow_ir(
    tc: TestCase,
    case_flows: dict[str, dict[str, Any]],
    profile_rules: list[AssertionRule],
    project: ProjectConfig,
) -> CaseFlowIR | None:
    flow = case_flows.get(tc.id)
    if not isinstance(flow, dict):
        return None

    steps: list[CaseFlowStepIR] = []
    for raw_step in flow.get("steps", []):
        if not isinstance(raw_step, dict):
            continue
        if "call" in raw_step:
            steps.append(CaseFlowStepIR(
                kind="call",
                call=raw_step.get("call", ""),
                args=list(raw_step.get("args", []) or []),
                kwargs=dict(raw_step.get("kwargs", {}) or {}),
                save_as=raw_step.get("save_as", "") or "",
            ))
        elif "assert" in raw_step:
            steps.append(CaseFlowStepIR(
                kind="assert",
                assertion=_case_flow_assertion_ir(
                    raw_step.get("assert", ""),
                    profile_rules,
                    project,
                ),
            ))
        elif "assign" in raw_step:
            steps.append(CaseFlowStepIR(
                kind="assign",
                target=raw_step.get("assign", "") or "",
                expr=raw_step.get("expr", "") or "",
            ))
        elif "comment" in raw_step:
            steps.append(CaseFlowStepIR(
                kind="comment",
                comment=raw_step.get("comment", "") or "",
            ))

    return CaseFlowIR(
        source=f"profile.case_flows.{tc.id}",
        fixture=flow.get("fixture", ""),
        object_name=flow.get("object", "") or "",
        steps=steps,
    )


def _case_flow_assertion_ir(
    assertion: str,
    profile_rules: list[AssertionRule],
    project: ProjectConfig,
) -> AssertionIR:
    clean = strip_backticks(assertion)
    if clean.startswith("assert "):
        return AssertionIR(
            source=assertion,
            kind="raw_python",
            code_lines=[clean],
            resolved_by="profile.case_flows.raw_assert",
        )
    code_lines, pattern_name = resolve_assertion(assertion, profile_rules, project)
    return AssertionIR(
        source=assertion,
        kind=_assertion_kind(pattern_name),
        code_lines=code_lines,
        resolved_by=pattern_name,
    )


def _assertion_kind(pattern_name: str) -> str:
    if pattern_name == "UNPARSED":
        return "unparsed"
    if pattern_name.startswith("profile:"):
        return "profile_rule"
    return "builtin_rule"
