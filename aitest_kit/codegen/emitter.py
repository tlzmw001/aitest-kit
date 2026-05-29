"""Deterministic pytest code emitter.

Transforms ParseResult (from parser.py) into pytest .py files using
rule-based assertion matching. Module-specific rules are loaded from
codegen_profile YAML blocks; everything else uses built-in patterns.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from aitest_kit.codegen.ir_renderer import EmitContext, render_file_from_ir
from aitest_kit.codegen.module_type import (
    resolve_module_type,
    validate_module_type_requirements,
)
from aitest_kit.codegen.parser import ParseResult, parse_case_file
from aitest_kit.codegen.planner import build_file_ir
from aitest_kit.codegen.profile import (
    load_profile_case_bodies,
    load_profile_case_fixtures,
    load_profile_case_flows,
    load_profile_extra_imports,
    load_profile_yaml,
    resolve_module_profile_path,
    load_profile_request_overrides,
    load_profile_rules,
    RuntimeProfile,
)
from aitest_kit.codegen.project_config import (
    DEFAULT_PROJECT,
    ProjectConfig,
)


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


def emit_file(
    parse_result: ParseResult,
    file_type: str,
    profile_path: str | Path | None = None,
    output_dir: str | Path = "test_workspace/tests/generated",
    fixture_dir: str | Path = "test_workspace/tests/fixtures",
    project: ProjectConfig | None = None,
    output_file_type: str | None = None,
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
    output_suffix = output_file_type or file_type
    output_path = output_dir / f"test_{module}_{output_suffix}.py"

    if output_path.exists():
        existing_source = _generated_source_path(output_path)
        if existing_source and existing_source != parse_result.source_file:
            return EmitResult(
                output_path=str(output_path),
                case_count=0,
                skipped=[],
                unparsed=[],
                manual_count=0,
                diagnostics=[
                    "E005: generated output conflict: "
                    f"{output_path} was generated from {existing_source}, "
                    f"not {parse_result.source_file}"
                ],
            )

    if isinstance(profile_path, RuntimeProfile) and profile_path.diagnostics:
        return EmitResult(
            output_path=str(output_path),
            case_count=0,
            skipped=[],
            unparsed=[],
            manual_count=0,
            diagnostics=list(profile_path.diagnostics),
        )

    profile_rules = load_profile_rules(profile_path) if profile_path else []
    request_overrides = load_profile_request_overrides(profile_path) if profile_path else {}
    extra_imports = load_profile_extra_imports(profile_path) if profile_path else []
    case_fixtures = load_profile_case_fixtures(profile_path) if profile_path else {}
    case_bodies = load_profile_case_bodies(profile_path) if profile_path else {}
    case_flows = load_profile_case_flows(profile_path) if profile_path else {}
    profile_data = load_profile_yaml(profile_path) if profile_path else {}
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
        fixture_dir=Path(fixture_dir),
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

    module_type_resolution = resolve_module_type(module, profile_data, proj)
    module_type_errors = [
        f"{diag.code}: {diag.message}"
        for diag in validate_module_type_requirements(
            module_type_resolution,
            proj,
            profile_data,
            case_bodies,
            case_flows,
        )
    ]
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
            and tc.id not in case_flows
        ]
        if uncovered:
            return EmitResult(
                output_path=str(output_path),
                case_count=0,
                skipped=[],
                unparsed=[],
                manual_count=0,
                diagnostics=[
                    "E002: 缺少基础请求体（HTTP），且以下用例未被 codegen_profile 的 case_bodies/case_flows 覆盖："
                    + ", ".join(uncovered)
                ],
            )

    file_ir = build_file_ir(
        parse_result,
        file_type,
        profile_path=profile_path,
        project=proj,
    )
    if file_ir.diagnostics:
        return EmitResult(
            output_path=str(output_path),
            case_count=0,
            skipped=[],
            unparsed=[],
            manual_count=0,
            diagnostics=[
                f"{diag.code}: {diag.message}" for diag in file_ir.diagnostics
            ],
        )

    rendered = render_file_from_ir(file_ir, parse_result.cases, ctx)
    if rendered.diagnostics:
        return EmitResult(
            output_path=str(output_path),
            case_count=0,
            skipped=[],
            unparsed=[],
            manual_count=0,
            diagnostics=rendered.diagnostics,
        )

    output_path.write_text("\n".join(rendered.lines), encoding="utf-8")

    return EmitResult(
        output_path=str(output_path),
        case_count=rendered.case_count,
        skipped=rendered.skipped,
        unparsed=rendered.unparsed,
        manual_count=rendered.manual_count,
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
    profile_path = resolve_module_profile_path(profile_dir, module)

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
            fixture_dir=profile_dir,
            project=project,
        )
        results.append(result)

    return results


def _generated_source_path(output_path: Path) -> str | None:
    try:
        first_line = output_path.read_text(encoding="utf-8").splitlines()[0]
    except (IndexError, OSError, UnicodeDecodeError):
        return None
    prefix = "# Auto-generated from "
    if not first_line.startswith(prefix):
        return None
    return first_line[len(prefix):]


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
