"""Render pytest files from Case IR."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aitest_kit.codegen.file_rendering import (
    render_base_request,
    render_header,
    render_req_helper,
)
from aitest_kit.codegen.flow_rendering import render_flow_call, request_var_name
from aitest_kit.codegen.function_rendering import render_case_function
from aitest_kit.codegen.ir import AssertionIR, CaseIR, FileIR, RequestIR
from aitest_kit.codegen.parser import SharedConfig, TestCase
from aitest_kit.codegen.project_config import AssertionRule, ProjectConfig
from aitest_kit.codegen.render_utils import (
    dict_to_python_compact,
    module_class_name,
    render_assignment,
    strip_backticks,
)
from aitest_kit.codegen.strategy import has_marker
from aitest_kit.registry.models import ModuleBinding


@dataclass
class EmitContext:
    module: str
    file_type: str
    source_path: str
    shared_config: SharedConfig
    project: ProjectConfig
    profile_rules: list[AssertionRule] = field(default_factory=list)
    extra_imports: list[str] = field(default_factory=list)
    case_bodies: dict[str, list[str]] = field(default_factory=dict)
    variables: dict[str, str] = field(default_factory=dict)
    module_binding: ModuleBinding | None = None


@dataclass
class RenderedFile:
    lines: list[str]
    case_count: int
    skipped: list[tuple[str, str]]
    unparsed: list[tuple[str, str]]
    manual_count: int
    diagnostics: list[str] = field(default_factory=list)


def _case_meta(tc: TestCase, ctx: EmitContext) -> dict[str, Any]:
    return {
        "tc_id": tc.id,
        "module": ctx.module,
        "category": ctx.file_type,
        "source": ctx.source_path,
        "title": tc.title,
        "priority": tc.priority,
        "markers": list(tc.markers),
    }


def _has_manual_marker(case_ir: CaseIR) -> bool:
    return has_marker(case_ir.markers, "manual")


def _render_setup_comments(tc: TestCase) -> list[str]:
    lines = []
    for key, val in tc.scenario_vars.items():
        if key.startswith("_"):
            continue
        lines.append(f"        # SETUP: {key}：{strip_backticks(val)}")
    return lines


def _render_req_call(request: RequestIR) -> str:
    kwargs = []
    if request.auto_fields:
        kwargs.append(f"auto_fields={dict_to_python_compact(request.auto_fields)}")
    overrides = dict_to_python_compact(request.overrides)
    if request.overrides:
        kwargs.append(f"overrides={overrides}")
    if request.patches:
        kwargs.append(f"patches={_render_request_patches(request)}")
    return "_req(" + ", ".join(kwargs) + ")"


def _render_request_patches(request: RequestIR) -> str:
    items: list[str] = []
    for patch in request.patches:
        parts = [
            f"'op': {dict_to_python_compact(patch.op)}",
            f"'path': {dict_to_python_compact(patch.path)}",
        ]
        if patch.has_value:
            parts.append(f"'value': {dict_to_python_compact(patch.value)}")
        elif patch.value_from:
            parts.append(f"'value': __tc_vars__[{dict_to_python_compact(patch.value_from)}]")
        items.append("{" + ", ".join(parts) + "}")
    return "[" + ", ".join(items) + "]"


def _render_assertions(assertions: list[AssertionIR]) -> list[str]:
    lines: list[str] = []
    for assertion in assertions:
        lines.extend(assertion.code_lines)
    return lines


def _unparsed_sources(assertions: list[AssertionIR]) -> list[str]:
    return [
        assertion.source
        for assertion in assertions
        if assertion.kind == "unparsed"
    ]


def _split_default_assertions(
    case_ir: CaseIR,
    ctx: EmitContext,
) -> tuple[list[AssertionIR], list[AssertionIR]]:
    if case_ir.strategy != "default_http":
        return [], case_ir.assertions
    common_count = len(ctx.shared_config.common_assertions)
    return case_ir.assertions[:common_count], case_ir.assertions[common_count:]


def _render_custom_body(case_ir: CaseIR, tc: TestCase, ctx: EmitContext) -> list[str]:
    fixtures = case_ir.fixtures or [f"setup_{ctx.module}"]
    body_lines: list[str] = []
    body_lines.extend(_render_setup_comments(tc))
    body_lines.append("")
    if fixtures:
        body_lines.append(f"        harness = {fixtures[0]}")
    body = case_ir.custom_body.lines if case_ir.custom_body else []
    for body_line in body:
        body_lines.append(f"        {body_line}" if body_line else "")
    return render_case_function(
        case_id=case_ir.case_id,
        title=case_ir.title,
        fixtures=fixtures,
        manual=_has_manual_marker(case_ir),
        metadata=_case_meta(tc, ctx),
        body_lines=body_lines,
    )


def _render_case_flow(
    case_ir: CaseIR,
    tc: TestCase,
    ctx: EmitContext,
) -> tuple[list[str], list[str], list[str]]:
    diagnostics: list[str] = []
    unparsed: list[str] = []
    body_lines: list[str] = []

    if case_ir.case_flow is None:
        return body_lines, unparsed, [
            f"E301: emitter cannot render {case_ir.case_id} without case_flow IR"
        ]

    if case_ir.profile_variables:
        body_lines.append(
            "        __tc_vars__ = resolve_profile_variables("
            f"{dict_to_python_compact(_profile_variable_specs(case_ir))})"
        )
    body_lines.extend(_render_setup_comments(tc))
    body_lines.append("")
    if case_ir.case_flow.object_name and case_ir.fixtures:
        fixture_name = case_ir.fixtures[0]
        if case_ir.case_flow.object_name != fixture_name:
            body_lines.append(f"        {case_ir.case_flow.object_name} = {fixture_name}")

    request_vars: dict[str, str] = {}
    for request_case_id, request_binding in case_ir.request_bindings.items():
        var_name = request_var_name(request_case_id)
        request_vars[request_case_id] = var_name
        body_lines.append(f"        {var_name} = {_render_req_call(request_binding)}")

    for step in case_ir.case_flow.steps:
        if step.kind == "call":
            body_lines.append(
                f"        {render_flow_call(step, current_case_id=case_ir.case_id, request_vars=request_vars)}"
            )
            continue
        if step.kind == "assert" and step.assertion is not None:
            for cl in step.assertion.code_lines:
                body_lines.append(f"        {cl}")
            if step.assertion.kind == "unparsed":
                unparsed.append(step.assertion.source)
            continue
        if step.kind == "assign":
            body_lines.append(f"        {step.target} = {step.expr}")
            continue
        if step.kind == "comment":
            comment = step.comment.strip()
            body_lines.append(f"        # {comment}")
            continue
        diagnostics.append(
            f"E301: emitter cannot render unsupported case_flow step in {case_ir.case_id}"
        )

    for assertion in case_ir.assertions:
        if assertion.kind != "structured_assertion":
            continue
        for cl in assertion.code_lines:
            body_lines.append(f"        {cl}")

    lines = render_case_function(
        case_id=case_ir.case_id,
        title=case_ir.title,
        fixtures=case_ir.fixtures,
        manual=_has_manual_marker(case_ir),
        metadata=_case_meta(tc, ctx),
        body_lines=body_lines,
    )
    return lines, unparsed, diagnostics


def _render_manual_body(case_ir: CaseIR, tc: TestCase, ctx: EmitContext) -> list[str]:
    body_lines: list[str] = []
    body_lines.extend(_render_setup_comments(tc))

    for assertion in case_ir.assertions:
        for cl in assertion.code_lines:
            body_lines.append(f"        {cl}")
    body_lines.append('        pytest.skip("manual check required")')
    return render_case_function(
        case_id=case_ir.case_id,
        title=case_ir.title,
        fixtures=case_ir.fixtures,
        manual=True,
        metadata=_case_meta(tc, ctx),
        body_lines=body_lines,
    )


def _profile_variable_specs(case_ir: CaseIR) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for item in case_ir.profile_variables:
        if item.provider == "env":
            specs[item.name] = {"env": item.env}
        elif item.provider == "value":
            specs[item.name] = {"value": item.value}
    return specs


def _render_default_body(
    case_ir: CaseIR,
    tc: TestCase,
    ctx: EmitContext,
) -> tuple[list[str], list[str], list[str]]:
    diagnostics: list[str] = []
    body_lines: list[str] = []
    unparsed: list[str] = []

    if case_ir.profile_variables:
        body_lines.append(
            "        __tc_vars__ = resolve_profile_variables("
            f"{dict_to_python_compact(_profile_variable_specs(case_ir))})"
        )
    body_lines.extend(_render_setup_comments(tc))

    if case_ir.request is None or case_ir.call is None:
        diagnostics.append(
            f"E301: emitter cannot render {case_ir.case_id} without request/call IR"
        )
        return body_lines, unparsed, diagnostics

    req_call = _render_req_call(case_ir.request)
    api_path = dict_to_python_compact(case_ir.call.api_path)
    body_lines.append("")
    body_lines.append(f"        __aitest_request = {req_call}")
    body_lines.append("        __aitest_response = None")
    body_lines.append("        try:")
    if case_ir.call.helper == "http_helper.post":
        body_lines.append('            if hasattr(http_helper, "post_response"):')
        body_lines.append(
            f"                __aitest_response = http_helper.post_response("
            f"{case_ir.call.target}, {api_path}, json=__aitest_request)"
        )
        body_lines.append("                __aitest_response.raise_for_status()")
        body_lines.append("                resp = __aitest_response.json()")
        body_lines.append("            else:")
        body_lines.append(
            f"                resp = {case_ir.call.helper}("
            f"{case_ir.call.target}, {api_path}, json=__aitest_request)"
        )
        body_lines.append("                __aitest_response = resp")
    else:
        body_lines.append(
            f"            resp = {case_ir.call.helper}("
            f"{case_ir.call.target}, {api_path}, json=__aitest_request)"
        )
        body_lines.append("            __aitest_response = resp")
    body_lines.append("        except Exception as exc:")
    body_lines.append(
        f'            capture_io(__tc_meta__["tc_id"], label={api_path}, protocol="http", '
        "request=__aitest_request, response=__aitest_response, exception=exc)"
    )
    body_lines.append("            raise")
    body_lines.append(
        f'        capture_io(__tc_meta__["tc_id"], label={api_path}, protocol="http", '
        "request=__aitest_request, response=__aitest_response)"
    )

    common_assertions, case_assertions = _split_default_assertions(case_ir, ctx)
    for cl in _render_assertions(common_assertions):
        body_lines.append(f"        {cl}")
    unparsed.extend(_unparsed_sources(common_assertions))

    for var in case_ir.variables:
        body_lines.append(f"        {var.name} = {var.expression}")

    for cl in _render_assertions(case_assertions):
        body_lines.append(f"        {cl}")
    unparsed.extend(_unparsed_sources(case_assertions))

    lines = render_case_function(
        case_id=case_ir.case_id,
        title=case_ir.title,
        fixtures=case_ir.fixtures,
        manual=_has_manual_marker(case_ir),
        metadata=_case_meta(tc, ctx),
        body_lines=body_lines,
    )
    return lines, unparsed, diagnostics


def _render_test_function(
    case_ir: CaseIR,
    tc: TestCase,
    ctx: EmitContext,
) -> tuple[list[str], list[str], list[str]]:
    if case_ir.strategy == "custom_case_body":
        return _render_custom_body(case_ir, tc, ctx), [], []
    if case_ir.strategy == "structured_case_flow":
        return _render_case_flow(case_ir, tc, ctx)
    if case_ir.strategy == "manual":
        return _render_manual_body(case_ir, tc, ctx), [], []
    return _render_default_body(case_ir, tc, ctx)


def render_file_from_ir(
    file_ir: FileIR,
    test_cases: list[TestCase],
    ctx: EmitContext,
) -> RenderedFile:
    """Render one pytest file from Case IR and parser case metadata."""
    tc_by_id = {tc.id: tc for tc in test_cases}
    all_lines: list[str] = []
    skipped: list[tuple[str, str]] = []
    skipped_meta: list[dict[str, Any]] = []
    all_unparsed: list[tuple[str, str]] = []
    manual_count = 0
    case_count = 0
    diagnostics: list[str] = []

    has_profile_variables = any(case.profile_variables for case in file_ir.cases)
    has_structured_assertions = any(
        assertion.kind == "structured_assertion"
        for case in file_ir.cases
        for assertion in case.assertions
    )
    has_default_http = any(case.strategy == "default_http" for case in file_ir.cases)
    has_module_harness = any(
        case.strategy in {"structured_case_flow", "custom_case_body"}
        for case in file_ir.cases
    )
    has_case_context = any(case.strategy != "skipped" for case in file_ir.cases)

    all_lines.extend(render_header(
        ctx,
        has_profile_variables=has_profile_variables,
        has_structured_assertions=has_structured_assertions,
        has_default_http=has_default_http,
        has_case_context=has_case_context,
        has_module_harness=has_module_harness,
    ))
    all_lines.extend(render_base_request(ctx))
    if ctx.shared_config.base_request_http:
        all_lines.extend(render_req_helper())

    class_name = module_class_name(ctx.module, ctx.file_type)
    category_label = {
        "business": "业务",
        "boundary": "边界",
    }.get(ctx.file_type, ctx.file_type)
    desc = f"{ctx.module} {category_label}测试用例"
    all_lines.extend(["", "", f"class {class_name}:"])
    all_lines.append(f'    """{desc}"""')

    cn_numbers = "一二三四五六七八九十"
    current_section = ""
    section_idx = 0

    for case_ir in file_ir.cases:
        tc = tc_by_id.get(case_ir.case_id)
        if tc is None:
            diagnostics.append(f"E301: emitter cannot find parser case for {case_ir.case_id}")
            continue

        if case_ir.strategy == "skipped":
            reason = case_ir.skip_reason or ""
            skipped.append((case_ir.case_id, reason))
            meta = _case_meta(tc, ctx)
            meta["reason"] = reason
            skipped_meta.append(meta)
            continue

        if _has_manual_marker(case_ir):
            manual_count += 1

        if case_ir.section and case_ir.section != current_section:
            current_section = case_ir.section
            cn_num = cn_numbers[section_idx] if section_idx < len(cn_numbers) else str(section_idx + 1)
            section_idx += 1
            all_lines.append("")
            all_lines.append(f"    # ── {cn_num}、{current_section} ──")

        all_lines.append("")
        func_lines, unparsed, func_diagnostics = _render_test_function(case_ir, tc, ctx)
        all_lines.extend(func_lines)
        diagnostics.extend(func_diagnostics)
        case_count += 1
        for assertion in unparsed:
            all_unparsed.append((case_ir.case_id, assertion))

    all_lines.append("")
    all_lines.append("")
    for tc_id, reason in skipped:
        all_lines.append(f"# SKIPPED: {tc_id} — {reason}")

    all_lines.append("")
    all_lines.extend(render_assignment("__codegen_skipped__", skipped_meta, indent=0))
    all_lines.append("")

    return RenderedFile(
        lines=all_lines,
        case_count=case_count,
        skipped=skipped,
        unparsed=all_unparsed,
        manual_count=manual_count,
        diagnostics=diagnostics,
    )
