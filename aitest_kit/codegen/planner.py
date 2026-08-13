"""Build Case IR from parser output and codegen configuration."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from aitest_kit.codegen.ir import (
    AssertionIR,
    CallIR,
    CaseIR,
    CustomBodyIR,
    DiagnosticIR,
    FileIR,
    RequestPatchIR,
    RequestIR,
    SourceTraceIR,
    VariableIR,
)
from aitest_kit.codegen.structured_assertions import (
    structured_assertion_metadata,
    structured_assertion_source,
    render_structured_assertion,
)
from aitest_kit.codegen.case_flow_planner import build_case_flow_ir
from aitest_kit.codegen.parser import ParseResult, TestCase
from aitest_kit.codegen.profile import (
    validate_case_flows,
    validate_profile_strategy_conflicts,
)
from aitest_kit.codegen.profile_variables import (
    case_flow_variable_refs,
    profile_variable_irs_for_case,
    request_variable_refs,
    validate_request_variable_references,
    validate_case_flow_variable_references,
    validate_profile_variables,
)
from aitest_kit.codegen.project_config import DEFAULT_PROJECT, AssertionRule, ProjectConfig
from aitest_kit.codegen.resolved_profile import resolve_profile
from aitest_kit.codegen.render_utils import (
    module_abbrev,
    resolve_assertion,
    strip_backticks,
    tc_number,
)
from aitest_kit.codegen.strategy import (
    STRATEGY_CUSTOM_CASE_BODY,
    STRATEGY_DEFAULT_HTTP,
    STRATEGY_MANUAL,
    STRATEGY_SKIPPED,
    STRATEGY_STRUCTURED_CASE_FLOW,
    resolve_case_strategy,
)
from aitest_kit.registry.models import ModuleBinding


def _is_protocol_key(key: str) -> bool:
    normalized = key.lower()
    return "协议" in key or "protocol" in normalized


def _grpc_source(tc: TestCase) -> tuple[bool, str, str]:
    for key, value in tc.scenario_vars.items():
        if _is_protocol_key(key) and "gRPC" in value:
            return True, f"scenario_vars.{key}", value
    return False, "", ""


def _fixtures_for(
    module: str,
    tc: TestCase,
    strategy: str,
    module_binding: ModuleBinding | None,
) -> tuple[list[str], str]:
    if strategy == STRATEGY_SKIPPED:
        return [], "skipped"
    if strategy == STRATEGY_CUSTOM_CASE_BODY:
        fixture = module_binding.fixture_name if module_binding else f"setup_{module}"
        return [fixture], "module binding"
    if strategy == STRATEGY_STRUCTURED_CASE_FLOW:
        fixture = module_binding.fixture_name if module_binding else f"setup_{module}"
        return [fixture], "module binding"
    if strategy == STRATEGY_MANUAL:
        return [], "manual marker"
    return ["http_base_url"], "default HTTP fixtures"


class _SafeFormatDict(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _format_auto_field(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return value.format_map(_SafeFormatDict(context))
    return value


def _auto_fields_for(
    module: str,
    category: str,
    tc: TestCase,
    project: ProjectConfig,
) -> dict[str, Any]:
    auto_fields = project.default_request.auto_fields
    if not auto_fields:
        return {}
    context = {
        "module": module,
        "module_abbrev": module_abbrev(module, project),
        "case_id": tc.id,
        "case_number": tc_number(tc.id),
        "category": category,
    }
    return {
        key: _format_auto_field(value, context)
        for key, value in auto_fields.items()
    }


def _request_for(
    module: str,
    category: str,
    tc: TestCase,
    project: ProjectConfig,
    requests: dict[str, dict[str, Any]],
) -> RequestIR | None:
    request = requests.get(tc.id, {})
    if request is None:
        request = {}
    if not isinstance(request, dict):
        return None
    auto_fields = _auto_fields_for(module, category, tc, project)
    overrides = dict(request.get("overrides", {}) or {})
    patches = _request_patches_for(request.get("patches", []) or [])
    return RequestIR(
        source=(
            "shared_config.base_request_http"
            " + project_config.default_request.auto_fields"
            " + profile.requests"
        ),
        auto_fields=auto_fields,
        overrides=overrides,
        patches=patches,
    )


def _request_patches_for(raw_patches: Any) -> list[RequestPatchIR]:
    if not isinstance(raw_patches, list):
        return []
    patches: list[RequestPatchIR] = []
    for patch in raw_patches:
        if not isinstance(patch, dict):
            continue
        patches.append(RequestPatchIR(
            op=str(patch.get("op", "") or ""),
            path=str(patch.get("path", "") or ""),
            value=patch.get("value"),
            has_value="value" in patch,
            value_from=str(patch.get("value_from", "") or ""),
        ))
    return patches


def _call_for(strategy: str, project: ProjectConfig) -> CallIR | None:
    if strategy in {
        STRATEGY_SKIPPED,
        STRATEGY_CUSTOM_CASE_BODY,
        STRATEGY_STRUCTURED_CASE_FLOW,
        STRATEGY_MANUAL,
    }:
        return None
    return CallIR(
        helper=project.helper_call,
        target="http_base_url",
        api_path=project.api_path,
    )


def _request_refs_in_value(value: Any, current_case_id: str) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        if set(value) == {"request_ref"}:
            ref = value.get("request_ref")
            if ref == "self":
                refs.add(current_case_id)
            elif isinstance(ref, str):
                refs.add(ref)
            return refs
        for item in value.values():
            refs.update(_request_refs_in_value(item, current_case_id))
    elif isinstance(value, list):
        for item in value:
            refs.update(_request_refs_in_value(item, current_case_id))
    return refs


def _request_refs_for_flow(flow: dict[str, Any], current_case_id: str) -> set[str]:
    refs: set[str] = set()
    steps = flow.get("steps")
    if not isinstance(steps, list):
        return refs
    for step in steps:
        refs.update(_request_refs_in_value(step, current_case_id))
    return refs


def _profile_variable_refs_for_case(
    case_id: str,
    case_flows: dict[str, dict[str, Any]],
    request_bindings: dict[str, RequestIR],
) -> set[str]:
    refs = case_flow_variable_refs(case_flows.get(case_id, {}))
    for request_binding in request_bindings.values():
        raw_request = {
            "patches": [
                {
                    **{"op": patch.op, "path": patch.path},
                    **({"value": patch.value} if patch.has_value else {}),
                    **({"value_from": patch.value_from} if patch.value_from else {}),
                }
                for patch in request_binding.patches
            ]
        }
        refs.update(request_variable_refs(raw_request))
    return refs


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
    if strategy == STRATEGY_SKIPPED:
        return []
    if strategy == STRATEGY_CUSTOM_CASE_BODY:
        return [
            AssertionIR(
                source=assertion,
                kind="custom_body",
                resolved_by=f"profile.case_bodies.{tc.id}",
            )
            for assertion in tc.assertions
        ]
    if strategy == STRATEGY_STRUCTURED_CASE_FLOW:
        return [
            AssertionIR(
                source=assertion,
                kind="case_flow",
                resolved_by=f"profile.case_flows.{tc.id}",
            )
            for assertion in tc.assertions
        ]
    if strategy == STRATEGY_MANUAL:
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


def _structured_assertions_for(
    tc: TestCase,
    strategy: str,
    structured_assertions: dict[str, list[dict[str, Any]]],
) -> list[AssertionIR]:
    if strategy not in {STRATEGY_DEFAULT_HTTP, STRATEGY_STRUCTURED_CASE_FLOW}:
        return []
    templates = structured_assertions.get(tc.id, [])
    result: list[AssertionIR] = []
    for template in templates:
        result.append(AssertionIR(
            source=structured_assertion_source(template),
            kind="structured_assertion",
            code_lines=render_structured_assertion(template),
            resolved_by=f"profile.structured_assertions.{tc.id}",
            metadata=structured_assertion_metadata(template),
        ))
    return result


def _case_diagnostics(case_ir: CaseIR, has_http_body: bool) -> list[DiagnosticIR]:
    diagnostics: list[DiagnosticIR] = []
    if case_ir.strategy == STRATEGY_DEFAULT_HTTP and not has_http_body:
        diagnostics.append(DiagnosticIR(
            code="E202",
            layer="planner",
            message="default strategy requires shared_config.base_request_http",
        ))
    if (
        case_ir.strategy == STRATEGY_STRUCTURED_CASE_FLOW
        and case_ir.request_bindings
        and not has_http_body
    ):
        diagnostics.append(DiagnosticIR(
            code="E202",
            layer="planner",
            message="case_flow request_ref requires shared_config.base_request_http",
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
    profile = resolve_profile(profile_path)
    profile_rules = profile.rules
    requests = profile.requests
    structured_assertions = profile.structured_assertions
    case_bodies = profile.case_bodies
    case_flows = profile.case_flows
    profile_variables = profile.variables

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
    file_ir.diagnostics.extend(
        DiagnosticIR(code="E202", layer="planner", message=error)
        for error in validate_profile_variables(profile_variables)
    )
    file_ir.diagnostics.extend(
        DiagnosticIR(code="E202", layer="planner", message=error)
        for error in validate_case_flow_variable_references(case_flows, profile_variables)
    )
    file_ir.diagnostics.extend(
        DiagnosticIR(code="E202", layer="planner", message=error)
        for error in validate_request_variable_references(requests, profile_variables)
    )

    cases_by_id = {tc.id: tc for tc in parse_result.cases}

    for tc in parse_result.cases:
        strategy_resolution = resolve_case_strategy(
            case_id=tc.id,
            markers=tc.markers,
            case_bodies=case_bodies,
            case_flows=case_flows,
        )
        strategy = strategy_resolution.final_strategy
        is_grpc, protocol_source, protocol_raw = _grpc_source(tc)
        if strategy == STRATEGY_CUSTOM_CASE_BODY:
            protocol = "custom"
        elif strategy == STRATEGY_STRUCTURED_CASE_FLOW:
            protocol = "flow"
        elif is_grpc:
            protocol = "grpc"
        else:
            protocol = "http"

        fixtures, fixtures_source = _fixtures_for(
            parse_result.module,
            tc,
            strategy,
            profile.module_binding,
        )
        request_refs: set[str] = set()
        if strategy == STRATEGY_DEFAULT_HTTP:
            request_refs.add(tc.id)
        if strategy == STRATEGY_STRUCTURED_CASE_FLOW:
            request_refs.update(_request_refs_for_flow(case_flows.get(tc.id, {}), tc.id))

        request_bindings: dict[str, RequestIR] = {}
        for request_case_id in sorted(request_refs):
            request_tc = cases_by_id.get(request_case_id)
            if request_tc is None:
                continue
            request_binding = _request_for(parse_result.module, category, request_tc, proj, requests)
            if request_binding is not None:
                request_bindings[request_case_id] = request_binding

        request = request_bindings.get(tc.id)
        call = _call_for(strategy, proj)
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
        template_assertions = _structured_assertions_for(tc, strategy, structured_assertions)
        assertions.extend(template_assertions)
        custom_body = None
        if strategy == STRATEGY_CUSTOM_CASE_BODY:
            custom_body = CustomBodyIR(
                source=f"profile.case_bodies.{tc.id}",
                fixtures=fixtures,
                lines=list(case_bodies.get(tc.id, [])),
            )
        case_flow = (
            build_case_flow_ir(
                tc,
                case_flows,
                profile_rules,
                proj,
                module_binding=profile.module_binding,
            )
            if strategy == STRATEGY_STRUCTURED_CASE_FLOW
            else None
        )
        case_profile_variables = profile_variable_irs_for_case(
            profile_variables,
            tc.id,
            _profile_variable_refs_for_case(tc.id, case_flows, request_bindings),
        )

        source_trace = {
            "strategy": SourceTraceIR(
                strategy,
                strategy_resolution.final_source,
                strategy_resolution.final_reason,
            ),
            "protocol": SourceTraceIR(
                protocol,
                protocol_source or "default",
                protocol_raw or "no gRPC marker",
            ),
            "fixtures": SourceTraceIR(fixtures, fixtures_source),
        }
        if request is not None and tc.id in requests:
            source_trace["requests"] = SourceTraceIR(
                requests[tc.id],
                f"profile.requests.{tc.id}",
            )
        if request is not None and proj.default_request.auto_fields:
            source_trace["default_request.auto_fields"] = SourceTraceIR(
                proj.default_request.auto_fields,
                "project_config.default_request.auto_fields",
            )
        if case_profile_variables:
            source_trace["profile_variables"] = SourceTraceIR(
                [item.name for item in case_profile_variables],
                "profile.variables",
                "case_flow {var: name} references",
            )
        if template_assertions:
            source_trace["structured_assertions"] = SourceTraceIR(
                len(template_assertions),
                f"profile.structured_assertions.{tc.id}",
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
            skip_reason=strategy_resolution.skip_reason,
            fixtures=fixtures,
            request=request,
            request_bindings=request_bindings,
            call=call,
            variables=variables,
            profile_variables=case_profile_variables,
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
