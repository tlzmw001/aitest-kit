"""Render pytest files from Case IR."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aitest_kit.codegen.ir import AssertionIR, CaseIR, FileIR, RequestIR
from aitest_kit.codegen.parser import SharedConfig, TestCase
from aitest_kit.codegen.project_config import AssertionRule, ProjectConfig
from aitest_kit.codegen.render_utils import (
    dict_to_python,
    dict_to_python_compact,
    module_class_name,
    render_assignment,
    strip_backticks,
    tc_func_name,
)


@dataclass
class EmitContext:
    module: str
    file_type: str
    source_path: str
    shared_config: SharedConfig
    project: ProjectConfig
    profile_rules: list[AssertionRule] = field(default_factory=list)
    request_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    extra_imports: list[str] = field(default_factory=list)
    case_fixtures: dict[str, list[str]] = field(default_factory=dict)
    case_bodies: dict[str, list[str]] = field(default_factory=dict)
    variables: dict[str, str] = field(default_factory=dict)
    fixture_dir: Path = field(default_factory=lambda: Path("test_workspace/tests/fixtures"))


@dataclass
class RenderedFile:
    lines: list[str]
    case_count: int
    skipped: list[tuple[str, str]]
    unparsed: list[tuple[str, str]]
    manual_count: int
    diagnostics: list[str] = field(default_factory=list)


def _render_header(ctx: EmitContext, has_grpc: bool = False) -> list[str]:
    lines = [
        f"# Auto-generated from {ctx.source_path}",
        f"# DO NOT EDIT — regenerate with: /test-codegen {ctx.module}",
        "import pytest",
        ctx.project.helper_import,
    ]
    if has_grpc:
        lines.append(ctx.project.grpc_helper_import)
    lines.extend(ctx.extra_imports)
    return lines


def _render_base_request(ctx: EmitContext) -> list[str]:
    body = ctx.shared_config.base_request_http
    if not body:
        return []
    lines = ["", ""]
    sanitized = dict(body)
    sanitized["user_id"] = None
    sanitized["reqId"] = None
    lines.append(f"BASE_REQUEST = {dict_to_python(sanitized)}")
    return lines


def _render_req_helper(ctx: EmitContext) -> list[str]:
    return [
        "",
        "",
        "def _req(user_id: str, req_id: str, **overrides) -> dict:",
        '    body = {**BASE_REQUEST, "user_id": user_id, "reqId": req_id}',
        "    body.update(overrides)",
        "    return body",
    ]


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
    return any("manual" in marker.lower() for marker in case_ir.markers)


def _render_setup_comments(tc: TestCase) -> list[str]:
    lines = []
    for key, val in tc.scenario_vars.items():
        if key.startswith("_"):
            continue
        lines.append(f"        # SETUP: {key}：{strip_backticks(val)}")
    return lines


def _render_req_call(request: RequestIR) -> str:
    if not request.overrides:
        return f'_req("{request.user_id}", "{request.req_id}")'

    overrides = dict_to_python_compact(request.overrides)
    return f'_req("{request.user_id}", "{request.req_id}", **{overrides})'


def _render_setup_call(case_ir: CaseIR) -> str | None:
    if case_ir.setup_call is None:
        return None
    if not case_ir.setup_call.kwargs:
        return f"{case_ir.setup_call.name}()"
    kwargs = ", ".join(
        f"{key}={dict_to_python_compact(value)}"
        for key, value in case_ir.setup_call.kwargs.items()
    )
    return f"{case_ir.setup_call.name}({kwargs})"


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
    if case_ir.strategy not in {"default_http", "default_grpc"}:
        return [], case_ir.assertions
    common_count = len(ctx.shared_config.common_assertions)
    return case_ir.assertions[:common_count], case_ir.assertions[common_count:]


def _render_custom_body(case_ir: CaseIR, tc: TestCase, ctx: EmitContext) -> list[str]:
    lines: list[str] = []
    if _has_manual_marker(case_ir):
        lines.append("    @pytest.mark.manual")

    fixtures = case_ir.fixtures or [f"setup_{ctx.module}"]
    signature = ", ".join(["self", *fixtures])
    lines.append(f"    def {tc_func_name(case_ir.case_id)}({signature}):")
    lines.append(f'        """{case_ir.case_id}：{case_ir.title}"""')
    lines.extend(render_assignment("__tc_meta__", _case_meta(tc, ctx), indent=2))
    lines.extend(_render_setup_comments(tc))
    lines.append("")
    body = case_ir.custom_body.lines if case_ir.custom_body else []
    for body_line in body:
        lines.append(f"        {body_line}" if body_line else "")
    return lines


def _render_flow_value(value: Any) -> str:
    if isinstance(value, dict):
        keys = set(value)
        if keys == {"ref"}:
            return str(value["ref"])
        if keys == {"expr"}:
            return str(value["expr"])
        pairs = [
            f"{dict_to_python_compact(key)}: {_render_flow_value(item)}"
            for key, item in value.items()
        ]
        return "{" + ", ".join(pairs) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_render_flow_value(item) for item in value) + "]"
    return dict_to_python_compact(value)


def _render_flow_call(step: Any) -> str:
    args = [_render_flow_value(item) for item in step.args]
    kwargs = [
        f"{key}={_render_flow_value(value)}"
        for key, value in step.kwargs.items()
    ]
    params = ", ".join([*args, *kwargs])
    call = f"{step.call}({params})"
    return f"{step.save_as} = {call}" if step.save_as else call


def _render_case_flow(
    case_ir: CaseIR,
    tc: TestCase,
    ctx: EmitContext,
) -> tuple[list[str], list[str], list[str]]:
    diagnostics: list[str] = []
    unparsed: list[str] = []
    lines: list[str] = []

    if case_ir.case_flow is None:
        return lines, unparsed, [
            f"E301: emitter cannot render {case_ir.case_id} without case_flow IR"
        ]

    if _has_manual_marker(case_ir):
        lines.append("    @pytest.mark.manual")

    signature = ", ".join(["self", *case_ir.fixtures])
    lines.append(f"    def {tc_func_name(case_ir.case_id)}({signature}):")
    lines.append(f'        """{case_ir.case_id}：{case_ir.title}"""')
    lines.extend(render_assignment("__tc_meta__", _case_meta(tc, ctx), indent=2))
    lines.extend(_render_setup_comments(tc))
    lines.append("")
    if case_ir.case_flow.object_name and case_ir.fixtures:
        fixture_name = case_ir.fixtures[0]
        if case_ir.case_flow.object_name != fixture_name:
            lines.append(f"        {case_ir.case_flow.object_name} = {fixture_name}")

    for step in case_ir.case_flow.steps:
        if step.kind == "call":
            lines.append(f"        {_render_flow_call(step)}")
            continue
        if step.kind == "assert" and step.assertion is not None:
            for cl in step.assertion.code_lines:
                lines.append(f"        {cl}")
            if step.assertion.kind == "unparsed":
                unparsed.append(step.assertion.source)
            continue
        if step.kind == "assign":
            lines.append(f"        {step.target} = {step.expr}")
            continue
        if step.kind == "comment":
            comment = step.comment.strip()
            lines.append(f"        # {comment}")
            continue
        diagnostics.append(
            f"E301: emitter cannot render unsupported case_flow step in {case_ir.case_id}"
        )

    return lines, unparsed, diagnostics


def _render_default_body(
    case_ir: CaseIR,
    tc: TestCase,
    ctx: EmitContext,
) -> tuple[list[str], list[str], list[str]]:
    diagnostics: list[str] = []
    lines: list[str] = []
    unparsed: list[str] = []

    if _has_manual_marker(case_ir):
        lines.append("    @pytest.mark.manual")

    signature = ", ".join(["self", *case_ir.fixtures])
    lines.append(f"    def {tc_func_name(case_ir.case_id)}({signature}):")
    lines.append(f'        """{case_ir.case_id}：{case_ir.title}"""')
    lines.extend(render_assignment("__tc_meta__", _case_meta(tc, ctx), indent=2))
    lines.extend(_render_setup_comments(tc))

    setup_call = _render_setup_call(case_ir)
    if setup_call:
        lines.append(f"        {setup_call}")

    if case_ir.request is None or case_ir.call is None:
        diagnostics.append(
            f"E301: emitter cannot render {case_ir.case_id} without request/call IR"
        )
        return lines, unparsed, diagnostics

    req_call = _render_req_call(case_ir.request)
    lines.append("")
    if case_ir.protocol == "grpc":
        lines.append(f"        resp = {case_ir.call.helper}({case_ir.call.target}, {req_call})")
    else:
        lines.append(
            f'        resp = {case_ir.call.helper}({case_ir.call.target}, '
            f'"{case_ir.call.api_path}", json={req_call})'
        )

    common_assertions, case_assertions = _split_default_assertions(case_ir, ctx)
    for cl in _render_assertions(common_assertions):
        lines.append(f"        {cl}")
    unparsed.extend(_unparsed_sources(common_assertions))

    for var in case_ir.variables:
        lines.append(f"        {var.name} = {var.expression}")

    for cl in _render_assertions(case_assertions):
        lines.append(f"        {cl}")
    unparsed.extend(_unparsed_sources(case_assertions))

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
    return _render_default_body(case_ir, tc, ctx)


def render_file_from_ir(
    file_ir: FileIR,
    test_cases: list[TestCase],
    ctx: EmitContext,
) -> RenderedFile:
    """Render one pytest file from Case IR and parser case metadata."""
    tc_by_id = {tc.id: tc for tc in test_cases}
    has_grpc = any(
        any("gRPC" in value for value in tc.scenario_vars.values())
        for tc in test_cases
        if not any("可行性存疑" in marker for marker in tc.markers)
    )

    all_lines: list[str] = []
    skipped: list[tuple[str, str]] = []
    skipped_meta: list[dict[str, Any]] = []
    all_unparsed: list[tuple[str, str]] = []
    manual_count = 0
    case_count = 0
    diagnostics: list[str] = []

    all_lines.extend(_render_header(ctx, has_grpc=has_grpc))
    all_lines.extend(_render_base_request(ctx))
    if ctx.shared_config.base_request_http:
        all_lines.extend(_render_req_helper(ctx))

    class_name = module_class_name(ctx.module, ctx.file_type)
    desc = f"{ctx.module} {'业务' if ctx.file_type == 'business' else '边界'}测试用例"
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
    fixture_path = ctx.fixture_dir / f"{ctx.module}.py"
    if not fixture_path.exists():
        all_lines.append(
            f"# TODO: setup_{ctx.module} fixture 需要手写实现（→ tests/fixtures/{ctx.module}.py）"
        )

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
