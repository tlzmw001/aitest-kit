"""Build Case IR from parser output and codegen configuration."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from aitest_kit.codegen.ir import (
    AssertionIR,
    CallIR,
    CaseFlowIR,
    CaseFlowStepIR,
    CaseIR,
    CustomBodyIR,
    DiagnosticIR,
    FileIR,
    RequestIR,
    SetupCallIR,
    SourceTraceIR,
    VariableIR,
)
from aitest_kit.codegen.parser import ParseResult, TestCase
from aitest_kit.codegen.profile import (
    load_profile_case_bodies,
    load_profile_case_fixtures,
    load_profile_case_flows,
    load_profile_request_overrides,
    load_profile_rules,
    validate_case_flows,
    validate_profile_strategy_conflicts,
)
from aitest_kit.codegen.project_config import DEFAULT_PROJECT, AssertionRule, ProjectConfig
from aitest_kit.codegen.render_utils import (
    module_abbrev,
    resolve_assertion,
    strip_backticks,
    tc_number,
)


def _has_marker(tc: TestCase, text: str) -> bool:
    needle = text.lower()
    return any(needle in marker.lower() for marker in tc.markers)


def _skip_reason(tc: TestCase) -> str | None:
    for marker in tc.markers:
        if "可行性存疑" in marker:
            return marker
    return None


def _grpc_source(tc: TestCase) -> tuple[bool, str, str]:
    for key, value in tc.scenario_vars.items():
        if "gRPC" in value:
            return True, f"scenario_vars.{key}", value
    return False, "", ""


def _strategy_for(
    tc: TestCase,
    case_bodies: dict[str, list[str]],
    case_flows: dict[str, dict[str, Any]],
) -> tuple[str, str, str]:
    reason = _skip_reason(tc)
    if reason:
        return "skipped", "markers", reason
    if tc.id in case_bodies:
        return "custom_case_body", f"profile.case_bodies.{tc.id}", "profile provides custom body"
    if tc.id in case_flows:
        return "structured_case_flow", f"profile.case_flows.{tc.id}", "profile provides structured flow"
    if _has_marker(tc, "manual"):
        return "manual", "markers", "manual marker"
    is_grpc, source, raw = _grpc_source(tc)
    if is_grpc:
        return "default_grpc", source, raw
    return "default_http", "default", "no custom strategy or gRPC marker"


def _fixtures_for(
    module: str,
    tc: TestCase,
    strategy: str,
    protocol: str,
    case_fixtures: dict[str, list[str]],
    case_flows: dict[str, dict[str, Any]],
) -> tuple[list[str], str]:
    if strategy == "skipped":
        return [], "skipped"
    if strategy == "custom_case_body":
        if tc.id in case_fixtures:
            return list(case_fixtures[tc.id]), f"profile.case_fixtures.{tc.id}"
        return [f"setup_{module}"], "default custom body fixture"
    if strategy == "structured_case_flow":
        fixture = case_flows.get(tc.id, {}).get("fixture")
        if isinstance(fixture, str) and fixture:
            return [fixture], f"profile.case_flows.{tc.id}.fixture"
        return [], f"profile.case_flows.{tc.id}.fixture"
    if protocol == "grpc":
        return ["grpc_target", f"setup_{module}"], "default gRPC fixtures"
    return ["http_base_url", f"setup_{module}"], "default HTTP fixtures"


def _request_for(
    module: str,
    tc: TestCase,
    strategy: str,
    project: ProjectConfig,
    request_overrides: dict[str, dict[str, Any]],
) -> RequestIR | None:
    if strategy in {"skipped", "custom_case_body", "structured_case_flow"}:
        return None

    abbrev = module_abbrev(module, project)
    num = tc_number(tc.id)
    default_user_id = f"u_{abbrev}_{num}"
    default_req_id = f"req_{abbrev}_{num}"
    configured = dict(request_overrides.get(tc.id, {}))
    user_id = configured.pop("user_id", default_user_id)
    req_id = configured.pop("reqId", configured.pop("req_id", default_req_id))
    return RequestIR(
        source="shared_config.base_request_http",
        user_id=user_id,
        req_id=req_id,
        overrides=configured,
    )


def _call_for(strategy: str, protocol: str, project: ProjectConfig) -> CallIR | None:
    if strategy in {"skipped", "custom_case_body", "structured_case_flow"}:
        return None
    if protocol == "grpc":
        return CallIR(helper=project.grpc_helper_call, target="grpc_target")
    return CallIR(
        helper=project.helper_call,
        target="http_base_url",
        api_path=project.api_path,
    )


def _needed_variables(assertions: list[str], variables: dict[str, str]) -> set[str]:
    needed = set()
    for assertion in assertions:
        clean = strip_backticks(assertion)
        for var_name in variables:
            if var_name in ("clamp(x)",):
                continue
            if re.search(rf"\b{re.escape(var_name)}\b", clean):
                needed.add(var_name)
    return needed


def _assertion_kind(pattern_name: str) -> str:
    if pattern_name == "UNPARSED":
        return "unparsed"
    if pattern_name.startswith("profile:"):
        return "profile_rule"
    return "builtin_rule"


def _assertion_ir(
    assertion: str,
    profile_rules: list[AssertionRule],
    project: ProjectConfig,
    variables: list[str],
) -> AssertionIR:
    code_lines, pattern_name = resolve_assertion(assertion, profile_rules, project)
    return AssertionIR(
        source=assertion,
        kind=_assertion_kind(pattern_name),
        code_lines=code_lines,
        resolved_by=pattern_name,
        variables=list(variables),
    )


def _variables_for_assertion(assertion: str, available: list[str]) -> list[str]:
    clean = strip_backticks(assertion)
    return [
        name for name in available
        if re.search(rf"\b{re.escape(name)}\b", clean)
    ]


def _assertions_for(
    tc: TestCase,
    strategy: str,
    common_assertions: list[str],
    profile_rules: list[AssertionRule],
    project: ProjectConfig,
    variables: list[str],
) -> list[AssertionIR]:
    if strategy == "skipped":
        return []
    if strategy == "custom_case_body":
        return [
            AssertionIR(
                source=assertion,
                kind="custom_body",
                resolved_by=f"profile.case_bodies.{tc.id}",
            )
            for assertion in tc.assertions
        ]
    if strategy == "structured_case_flow":
        return [
            AssertionIR(
                source=assertion,
                kind="case_flow",
                resolved_by=f"profile.case_flows.{tc.id}",
            )
            for assertion in tc.assertions
        ]
    if strategy == "manual":
        return [
            AssertionIR(
                source=assertion,
                kind="manual_comment",
                code_lines=[f"# MANUAL CHECK: {strip_backticks(assertion)}"],
                resolved_by="manual marker",
            )
            for assertion in tc.assertions
        ]

    result: list[AssertionIR] = []
    for assertion in common_assertions:
        result.append(_assertion_ir(
            assertion,
            profile_rules,
            project,
            _variables_for_assertion(assertion, variables),
        ))
    for assertion in tc.assertions:
        result.append(_assertion_ir(
            assertion,
            profile_rules,
            project,
            _variables_for_assertion(assertion, variables),
        ))
    return result


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


def _case_flow_for(
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


def _case_diagnostics(case_ir: CaseIR, has_http_body: bool) -> list[DiagnosticIR]:
    diagnostics: list[DiagnosticIR] = []
    if case_ir.strategy in {"default_http", "default_grpc", "manual"} and not has_http_body:
        diagnostics.append(DiagnosticIR(
            code="E202",
            layer="planner",
            message="default strategy requires shared_config.base_request_http",
        ))
    for assertion in case_ir.assertions:
        if assertion.kind == "unparsed":
            diagnostics.append(DiagnosticIR(
                code="E203",
                layer="planner",
                message=f"assertion unresolved: {assertion.source}",
            ))
    return diagnostics


def build_file_ir(
    parse_result: ParseResult,
    category: str,
    profile_path: str | Path | None = None,
    project: ProjectConfig | None = None,
) -> FileIR:
    """Build Case IR for one parsed Markdown file."""
    proj = project or DEFAULT_PROJECT
    profile_rules = load_profile_rules(profile_path) if profile_path else []
    request_overrides = load_profile_request_overrides(profile_path) if profile_path else {}
    case_fixtures = load_profile_case_fixtures(profile_path) if profile_path else {}
    case_bodies = load_profile_case_bodies(profile_path) if profile_path else {}
    case_flows = load_profile_case_flows(profile_path) if profile_path else {}

    file_ir = FileIR(
        module=parse_result.module,
        category=category,
        source_file=parse_result.source_file,
        diagnostics=[
            DiagnosticIR(code="E001", layer="parser", message=error)
            for error in parse_result.errors
        ],
    )
    file_ir.diagnostics.extend(
        DiagnosticIR(code="E202", layer="planner", message=error)
        for error in validate_profile_strategy_conflicts(case_bodies, case_flows)
    )
    file_ir.diagnostics.extend(
        DiagnosticIR(code="E202", layer="planner", message=error)
        for error in validate_case_flows(case_flows)
    )

    for tc in parse_result.cases:
        strategy, strategy_source, strategy_reason = _strategy_for(tc, case_bodies, case_flows)
        is_grpc, protocol_source, protocol_raw = _grpc_source(tc)
        if strategy == "custom_case_body":
            protocol = "custom"
        elif strategy == "structured_case_flow":
            protocol = "flow"
        elif is_grpc:
            protocol = "grpc"
        else:
            protocol = "http"

        fixtures, fixtures_source = _fixtures_for(
            parse_result.module,
            tc,
            strategy,
            protocol,
            case_fixtures,
            case_flows,
        )
        request = _request_for(parse_result.module, tc, strategy, proj, request_overrides)
        call = _call_for(strategy, protocol, proj)
        needed = _needed_variables(tc.assertions, parse_result.shared_config.variables)
        variables = [
            VariableIR(name=name, expression=proj.var_map[name], source="project_config.var_map")
            for name in proj.var_map
            if name in needed
        ]
        assertions = _assertions_for(
            tc,
            strategy,
            parse_result.shared_config.common_assertions,
            profile_rules,
            proj,
            [var.name for var in variables],
        )
        custom_body = None
        if strategy == "custom_case_body":
            custom_body = CustomBodyIR(
                source=f"profile.case_bodies.{tc.id}",
                fixtures=fixtures,
                lines=list(case_bodies.get(tc.id, [])),
            )
        case_flow = (
            _case_flow_for(tc, case_flows, profile_rules, proj)
            if strategy == "structured_case_flow"
            else None
        )

        source_trace = {
            "strategy": SourceTraceIR(strategy, strategy_source, strategy_reason),
            "protocol": SourceTraceIR(
                protocol,
                protocol_source or "default",
                protocol_raw or "no gRPC marker",
            ),
            "fixtures": SourceTraceIR(fixtures, fixtures_source),
        }
        if request is not None and tc.id in request_overrides:
            source_trace["request_overrides"] = SourceTraceIR(
                request_overrides[tc.id],
                f"profile.request_overrides.{tc.id}",
            )

        case_ir = CaseIR(
            case_id=tc.id,
            title=tc.title,
            module=parse_result.module,
            category=category,
            source_file=parse_result.source_file,
            section=tc.section,
            priority=tc.priority,
            markers=list(tc.markers),
            strategy=strategy,
            protocol=protocol,
            skip_reason=_skip_reason(tc),
            fixtures=fixtures,
            setup_call=(
                SetupCallIR(name=f"setup_{parse_result.module}", kwargs={"case_id": tc.id})
                if strategy in {"default_http", "default_grpc", "manual"}
                else None
            ),
            request=request,
            call=call,
            variables=variables,
            assertions=assertions,
            custom_body=custom_body,
            case_flow=case_flow,
            source_trace=source_trace,
        )
        case_ir.diagnostics.extend(
            _case_diagnostics(case_ir, parse_result.shared_config.base_request_http is not None)
        )
        file_ir.cases.append(case_ir)

    return file_ir
