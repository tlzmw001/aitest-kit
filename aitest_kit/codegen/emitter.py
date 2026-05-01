"""Deterministic pytest code emitter.

Transforms ParseResult (from parser.py) into pytest .py files using
rule-based assertion matching. Module-specific rules are loaded from
codegen_profile YAML blocks; everything else uses built-in patterns.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aitest_kit.codegen.parser import ParseResult, SharedConfig, TestCase, parse_case_file
from aitest_kit.codegen.profile import (
    load_profile_case_bodies,
    load_profile_case_fixtures,
    load_profile_extra_imports,
    load_profile_module_type,
    load_profile_request_overrides,
    load_profile_rules,
)
from aitest_kit.codegen.project_config import (
    DEFAULT_PROJECT,
    AssertionRule,
    ProjectConfig,
)
from aitest_kit.codegen.render_utils import (
    dict_to_python,
    dict_to_python_compact,
    resolve_assertion,
    strip_backticks,
)


# ---------------------------------------------------------------------------
# Code generation context
# ---------------------------------------------------------------------------

@dataclass
class EmitContext:
    module: str
    file_type: str  # "business" or "boundary"
    source_path: str
    shared_config: SharedConfig
    project: ProjectConfig = field(default_factory=ProjectConfig)
    profile_rules: list[AssertionRule] = field(default_factory=list)
    request_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    extra_imports: list[str] = field(default_factory=list)
    case_fixtures: dict[str, list[str]] = field(default_factory=dict)
    case_bodies: dict[str, list[str]] = field(default_factory=dict)
    variables: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# File-level template rendering
# ---------------------------------------------------------------------------

def _module_class_name(module: str, file_type: str) -> str:
    parts = module.split("_")
    camel = "".join(p.capitalize() for p in parts)
    suffix = "Business" if file_type == "business" else "Boundary"
    return f"Test{camel}{suffix}"


def _tc_func_name(tc_id: str) -> str:
    return "test_" + tc_id.lower().replace("-", "_")


def _tc_number(tc_id: str) -> str:
    m = re.search(r"(\d+)$", tc_id)
    return m.group(1) if m else "000"


def _module_abbrev(module: str, project: ProjectConfig) -> str:
    """Short abbreviation for user_id/req_id generation."""
    return project.module_abbrevs.get(module, module[:4])


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


# ---------------------------------------------------------------------------
# Test function rendering
# ---------------------------------------------------------------------------

def _needs_variables(assertions: list[str], variables: dict[str, str]) -> set[str]:
    """Determine which shared variables are referenced by assertions."""
    needed = set()
    for a in assertions:
        clean = strip_backticks(a)
        for var_name in variables:
            if var_name in ("clamp(x)",):
                continue
            if re.search(rf"\b{re.escape(var_name)}\b", clean):
                needed.add(var_name)
    return needed


def _render_req_call(tc: TestCase, ctx: EmitContext, default_user_id: str, default_req_id: str) -> str:
    """Render _req(...) using optional profile-specified case overrides."""
    configured = dict(ctx.request_overrides.get(tc.id, {}))
    user_id = configured.pop("user_id", default_user_id)
    req_id = configured.pop("reqId", configured.pop("req_id", default_req_id))

    if not configured:
        return f'_req("{user_id}", "{req_id}")'

    return f'_req("{user_id}", "{req_id}", **{dict_to_python_compact(configured)})'


def _render_test_function(tc: TestCase, ctx: EmitContext) -> list[str]:
    """Render a single test function."""
    abbrev = _module_abbrev(ctx.module, ctx.project)
    num = _tc_number(tc.id)
    func_name = _tc_func_name(tc.id)
    is_manual = any("manual" in m.lower() for m in tc.markers)
    is_grpc = any("gRPC" in v for v in tc.scenario_vars.values())

    lines = []

    # Decorator
    if is_manual:
        lines.append("    @pytest.mark.manual")

    custom_body = ctx.case_bodies.get(tc.id)
    if custom_body is not None:
        fixtures = ctx.case_fixtures.get(tc.id, [f"setup_{ctx.module}"])
        signature = ", ".join(["self", *fixtures])
        lines.append(f"    def {func_name}({signature}):")
        lines.append(f'        """{tc.id}：{tc.title}"""')
        for key, val in tc.scenario_vars.items():
            if key.startswith("_"):
                continue
            lines.append(f"        # SETUP: {key}：{strip_backticks(val)}")
        lines.append("")
        for body_line in custom_body:
            lines.append(f"        {body_line}" if body_line else "")
        return lines, []

    # Function signature
    if is_grpc:
        lines.append(f"    def {func_name}(self, grpc_target, setup_{ctx.module}):")
    else:
        lines.append(f"    def {func_name}(self, http_base_url, setup_{ctx.module}):")
    lines.append(f'        """{tc.id}：{tc.title}"""')

    # Setup comments + fixture call
    for key, val in tc.scenario_vars.items():
        if key.startswith("_"):
            continue
        lines.append(f"        # SETUP: {key}：{strip_backticks(val)}")
    lines.append(f'        setup_{ctx.module}(case_id="{tc.id}")')

    # Request
    user_id = f"u_{abbrev}_{num}"
    req_id = f"req_{abbrev}_{num}"
    req_call = _render_req_call(tc, ctx, user_id, req_id)
    lines.append("")
    if is_grpc:
        lines.append(
            f'        resp = {ctx.project.grpc_helper_call}(grpc_target, '
            f'{req_call})'
        )
    else:
        lines.append(
            f'        resp = {ctx.project.helper_call}(http_base_url, "{ctx.project.api_path}", '
            f'json={req_call})'
        )

    # Common assertions (skip for manual)
    if not is_manual:
        for ca in ctx.shared_config.common_assertions:
            code_lines, _ = resolve_assertion(ca, ctx.profile_rules, ctx.project)
            for cl in code_lines:
                lines.append(f"        {cl}")

    # Variable extraction (only if assertions reference them)
    needed_vars = _needs_variables(tc.assertions, ctx.variables)
    for var_name in ctx.project.var_map:
        if var_name in needed_vars:
            lines.append(f"        {var_name} = {ctx.project.var_map[var_name]}")

    # Case-specific assertions
    unparsed = []
    for assertion in tc.assertions:
        if is_manual:
            lines.append(f"        # MANUAL CHECK: {strip_backticks(assertion)}")
            continue

        code_lines, pattern_name = resolve_assertion(
            assertion, ctx.profile_rules, ctx.project
        )
        for cl in code_lines:
            lines.append(f"        {cl}")
        if pattern_name == "UNPARSED":
            unparsed.append(assertion)

    return lines, unparsed


# ---------------------------------------------------------------------------
# File-level emit
# ---------------------------------------------------------------------------

@dataclass
class EmitResult:
    output_path: str
    case_count: int
    skipped: list[tuple[str, str]]  # (tc_id, reason)
    unparsed: list[tuple[str, str]]  # (tc_id, assertion_text)
    manual_count: int
    diagnostics: list[str] = field(default_factory=list)


def _module_type_diagnostics(
    module_type: str | None,
    project: ProjectConfig,
    case_bodies: dict[str, list[str]],
) -> list[str]:
    if not module_type:
        return []

    module_type_cfg = project.module_types.get(module_type)
    if module_type_cfg is None:
        return [f"E003: codegen_profile 声明了未知 module_type={module_type}"]

    diagnostics: list[str] = []
    for required in module_type_cfg.get("requires", []):
        if required == "case_bodies" and not case_bodies:
            diagnostics.append(
                f"E004: module_type={module_type} 要求 codegen_profile 提供 case_bodies"
            )
    return diagnostics


def emit_file(
    parse_result: ParseResult,
    file_type: str,
    profile_path: str | Path | None = None,
    output_dir: str | Path = "test_workspace/tests/generated",
    project: ProjectConfig | None = None,
) -> EmitResult:
    """Emit a pytest file from a ParseResult.

    Args:
        parse_result: Output from parser.parse_case_file()
        file_type: "business" or "boundary"
        profile_path: Path to codegen_profile_{module}.md (optional)
        output_dir: Directory for generated .py files
    """
    module = parse_result.module
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"test_{module}_{file_type}.py"

    profile_rules = load_profile_rules(profile_path) if profile_path else []
    request_overrides = load_profile_request_overrides(profile_path) if profile_path else {}
    extra_imports = load_profile_extra_imports(profile_path) if profile_path else []
    case_fixtures = load_profile_case_fixtures(profile_path) if profile_path else {}
    case_bodies = load_profile_case_bodies(profile_path) if profile_path else {}
    module_type = load_profile_module_type(profile_path) if profile_path else None
    proj = project or DEFAULT_PROJECT

    ctx = EmitContext(
        module=module,
        file_type=file_type,
        source_path=parse_result.source_file,
        shared_config=parse_result.shared_config,
        project=proj,
        profile_rules=profile_rules,
        request_overrides=request_overrides,
        extra_imports=extra_imports,
        case_fixtures=case_fixtures,
        case_bodies=case_bodies,
        variables=parse_result.shared_config.variables,
    )

    if parse_result.errors:
        return EmitResult(
            output_path=str(output_path),
            case_count=0,
            skipped=[],
            unparsed=[],
            manual_count=0,
            diagnostics=list(parse_result.errors),
        )

    module_type_errors = _module_type_diagnostics(module_type, proj, case_bodies)
    if module_type_errors:
        return EmitResult(
            output_path=str(output_path),
            case_count=0,
            skipped=[],
            unparsed=[],
            manual_count=0,
            diagnostics=module_type_errors,
        )

    if ctx.shared_config.base_request_http is None:
        uncovered = [
            tc.id for tc in parse_result.cases
            if not any("可行性存疑" in m for m in tc.markers)
            and tc.id not in ctx.case_bodies
        ]
        if uncovered:
            return EmitResult(
                output_path=str(output_path),
                case_count=0,
                skipped=[],
                unparsed=[],
                manual_count=0,
                diagnostics=[
                    "E002: 缺少基础请求体（HTTP），且以下用例未被 codegen_profile 的 case_bodies 覆盖："
                    + ", ".join(uncovered)
                ],
            )

    all_lines: list[str] = []
    skipped: list[tuple[str, str]] = []
    all_unparsed: list[tuple[str, str]] = []
    manual_count = 0
    case_count = 0

    has_grpc = any(
        any("gRPC" in v for v in tc.scenario_vars.values())
        for tc in parse_result.cases
        if not any("可行性存疑" in m for m in tc.markers)
    )

    # Header
    all_lines.extend(_render_header(ctx, has_grpc=has_grpc))

    # BASE_REQUEST
    all_lines.extend(_render_base_request(ctx))

    # _req helper
    if ctx.shared_config.base_request_http:
        all_lines.extend(_render_req_helper(ctx))

    # Class
    class_name = _module_class_name(module, file_type)
    desc = f"{module} {'业务' if file_type == 'business' else '边界'}测试用例"
    all_lines.extend(["", "", f"class {class_name}:"])
    all_lines.append(f'    """{desc}"""')

    _CN_NUMBERS = "一二三四五六七八九十"

    current_section = ""
    section_idx = 0

    for tc in parse_result.cases:
        # Skip feasibility-questioned cases
        skip_markers = [m for m in tc.markers if "可行性存疑" in m]
        if skip_markers:
            reason = skip_markers[0]
            skipped.append((tc.id, reason))
            continue

        is_manual = any("manual" in m.lower() for m in tc.markers)
        if is_manual:
            manual_count += 1

        # Section comment
        if tc.section and tc.section != current_section:
            current_section = tc.section
            cn_num = _CN_NUMBERS[section_idx] if section_idx < len(_CN_NUMBERS) else str(section_idx + 1)
            section_idx += 1
            all_lines.append("")
            all_lines.append(f"    # ── {cn_num}、{current_section} ──")

        all_lines.append("")
        func_lines, unparsed = _render_test_function(tc, ctx)
        all_lines.extend(func_lines)
        case_count += 1

        for u in unparsed:
            all_unparsed.append((tc.id, u))

    # Footer: TODO + SKIPPED
    all_lines.append("")
    all_lines.append("")
    fixture_path = Path("test_workspace/tests/fixtures") / f"{module}.py"
    if not fixture_path.exists():
        all_lines.append(
            f"# TODO: setup_{module} fixture 需要手写实现（→ tests/fixtures/{module}.py）"
        )

    for tc_id, reason in skipped:
        all_lines.append(f"# SKIPPED: {tc_id} — {reason}")

    all_lines.append("")

    output_path.write_text("\n".join(all_lines), encoding="utf-8")

    return EmitResult(
        output_path=str(output_path),
        case_count=case_count,
        skipped=skipped,
        unparsed=all_unparsed,
        manual_count=manual_count,
    )


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def emit_module(
    module: str,
    cases_dir: str | Path = "test_workspace/cases",
    output_dir: str | Path = "test_workspace/tests/generated",
    profile_dir: str | Path = "test_workspace/tests/fixtures",
    project: ProjectConfig | None = None,
) -> list[EmitResult]:
    """Emit all files for a module. Returns list of EmitResult."""
    cases_dir = Path(cases_dir)
    profile_path = Path(profile_dir) / f"codegen_profile_{module}.md"
    if not profile_path.exists():
        profile_path = None

    results = []
    for file_type in ("business", "boundary"):
        md_path = cases_dir / module / f"{file_type}.md"
        if not md_path.exists():
            continue
        parse_result = parse_case_file(str(md_path))
        result = emit_file(
            parse_result,
            file_type,
            profile_path=profile_path,
            output_dir=output_dir,
            project=project,
        )
        results.append(result)

    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m aitest_kit.codegen.emitter <module>")
        sys.exit(1)

    module = sys.argv[1]
    results = emit_module(module)
    for r in results:
        print(f"\n{r.output_path}")
        print(f"  Cases: {r.case_count}")
        print(f"  Manual: {r.manual_count}")
        print(f"  Skipped: {len(r.skipped)}")
        if r.skipped:
            for tc_id, reason in r.skipped:
                print(f"    {tc_id}: {reason}")
        print(f"  Unparsed: {len(r.unparsed)}")
        if r.unparsed:
            for tc_id, text in r.unparsed:
                print(f"    {tc_id}: {text}")
        if r.diagnostics:
            print(f"  Diagnostics: {len(r.diagnostics)}")
            for diag in r.diagnostics:
                print(f"    {diag}")
