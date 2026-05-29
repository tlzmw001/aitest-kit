"""CLI-facing operations for case-suite codegen mode."""
from __future__ import annotations

import ast
import difflib
import json
import tempfile
from pathlib import Path
from typing import Any

import click
import yaml

from aitest_kit.codegen.emitter import emit_file
from aitest_kit.codegen.health import (
    build_suite_codegen_health_report,
    codegen_health_to_dict,
    write_codegen_health_report,
)
from aitest_kit.codegen.ir import ir_to_dict
from aitest_kit.codegen.parser import ParseResult
from aitest_kit.codegen.planner import build_file_ir
from aitest_kit.codegen.promotion import (
    analyze_case_body_promotion,
    promotion_to_dict,
    write_promotion_patch,
    write_promotion_report,
)
from aitest_kit.codegen.profile_validator import (
    validate_profile_suite,
    write_profile_validation_report,
)
from aitest_kit.codegen.project_config import ProjectConfig
from aitest_kit.codegen.suite import SuiteContext, load_suite_context, parse_suite_case_file


def _suite_output_file_type(context: SuiteContext, case_path: Path) -> str:
    return f"{context.suite}_{case_path.stem}"


def run_suite_codegen(
    cases_path: str,
    *,
    module_override: str | None,
    paths: Any,
    project: ProjectConfig,
    dry_run: bool,
    check: bool,
    dump_ir: bool,
    explain: str | None,
    analyze_promotion: bool,
    suggest_promotion_patch: bool,
    validate_profile: bool,
    health_report: bool,
    write_report: bool,
    report_dir: str | None,
) -> int:
    """Run codegen in case-suite mode."""
    if validate_profile:
        report = validate_profile_suite(
            cases_path,
            module=module_override,
            profile_dir=paths.profile_dir,
            project=project,
        )
        _print_suite_validation(report)
        if write_report:
            out_dir = Path(report_dir) if report_dir else paths.reports_dir / "codegen" / "latest"
            written = write_profile_validation_report(report, out_dir)
            click.echo("Profile validation artifacts written:")
            for path in written.values():
                click.echo(f"- {path}")
        return 1 if report.errors else 0

    gate_result = _suite_profile_gate(cases_path, module_override, paths, project)
    if gate_result:
        return gate_result

    context = load_suite_context(
        cases_path,
        module_override=module_override,
        profile_dir=paths.profile_dir,
    )
    if check:
        return _check_suite_consistency(context, paths, project)
    if dump_ir:
        return _dump_suite_ir(context, project)
    if explain:
        return _explain_suite_case(context, explain, project)
    if health_report:
        return _suite_health_report(context, paths, project, write_report, report_dir)
    if analyze_promotion or suggest_promotion_patch:
        return _analyze_suite_promotion(
            context,
            paths,
            write_report=write_report or suggest_promotion_patch,
            write_patch=suggest_promotion_patch,
            report_dir=report_dir,
            echo_yaml=analyze_promotion,
        )
    if dry_run:
        return _dry_run_suite(context)
    return _generate_suite(context, paths, project)


def _print_suite_validation(report: Any) -> None:
    click.echo(f"\nSuite: {report.suite}")
    click.echo(f"  Module: {report.module}")
    click.echo(f"  Profile: {report.profile_path}")
    click.echo(f"  Case files: {len(report.case_files)}")
    click.echo(f"  Cases: {len(report.case_ids)}")
    if report.diagnostics:
        click.echo("  Diagnostics:")
        for diag in report.diagnostics:
            click.echo(f"    {diag.format()}")
    else:
        click.echo("  Status: OK")
    click.echo(
        f"\nProfile validation summary: suites=1, "
        f"errors={len(report.errors)}, warnings={len(report.warnings)}"
    )


def _suite_profile_gate(
    cases_path: str,
    module_override: str | None,
    paths: Any,
    project: ProjectConfig,
) -> int:
    report = validate_profile_suite(
        cases_path,
        module=module_override,
        profile_dir=paths.profile_dir,
        project=project,
    )
    if not report.errors:
        return 0
    click.echo(
        f"Profile gate: suites=1, errors={len(report.errors)}, "
        f"warnings={len(report.warnings)}"
    )
    click.echo("Profile gate blocked codegen:")
    click.echo(f"\nSuite: {report.suite}")
    for diag in report.errors:
        click.echo(f"  {diag.format()}")
    click.echo("\nRun `aitest codegen --cases <dir> --validate-profile --write-report` for artifacts.")
    return 1


def _parse_suite_files(context: SuiteContext) -> list[tuple[Path, ParseResult]]:
    return [
        (path, parse_suite_case_file(path, context.module))
        for path in context.case_files
    ]


def _dump_suite_ir(context: SuiteContext, project: ProjectConfig) -> int:
    payload = {
        "suites": [
            {
                "module": context.module,
                "suite": context.suite,
                "files": [
                    ir_to_dict(build_file_ir(
                        parse_result,
                        path.stem,
                        profile_path=context.runtime_profile,
                        project=project,
                    ))
                    for path, parse_result in _parse_suite_files(context)
                ],
            }
        ]
    }
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _explain_suite_case(context: SuiteContext, case_id: str, project: ProjectConfig) -> int:
    for path, parse_result in _parse_suite_files(context):
        file_ir = build_file_ir(
            parse_result,
            path.stem,
            profile_path=context.runtime_profile,
            project=project,
        )
        for case_ir in file_ir.cases:
            if case_ir.case_id == case_id:
                click.echo(yaml.safe_dump(
                    ir_to_dict(case_ir),
                    allow_unicode=True,
                    sort_keys=False,
                ).rstrip())
                return 0
    click.echo(f"Case {case_id} not found in suite {context.suite}")
    return 1


def _suite_health_report(
    context: SuiteContext,
    paths: Any,
    project: ProjectConfig,
    write_report: bool,
    report_dir: str | None,
) -> int:
    report = build_suite_codegen_health_report(context, project=project)
    click.echo(yaml.safe_dump(
        codegen_health_to_dict(report),
        allow_unicode=True,
        sort_keys=False,
    ).rstrip())
    if write_report:
        out_dir = Path(report_dir) if report_dir else paths.reports_dir / "codegen" / "latest"
        written = write_codegen_health_report(report, out_dir)
        click.echo("Codegen health artifacts written:")
        for path in written.values():
            click.echo(f"- {path}")
    return 1 if report.error_count else 0


def _analyze_suite_promotion(
    context: SuiteContext,
    paths: Any,
    *,
    write_report: bool,
    write_patch: bool,
    report_dir: str | None,
    echo_yaml: bool,
) -> int:
    case_ids = {
        tc.id
        for _, parse_result in _parse_suite_files(context)
        for tc in parse_result.cases
    }
    report = analyze_case_body_promotion(
        context.module,
        context.runtime_profile,
        suite=context.suite,
        case_ids=case_ids,
    )
    if echo_yaml:
        click.echo(yaml.safe_dump(
            {"promotion_reports": [promotion_to_dict(report)]},
            allow_unicode=True,
            sort_keys=False,
        ).rstrip())

    written: list[Path] = []
    if write_report:
        out_dir = Path(report_dir) if report_dir else paths.reports_dir / "codegen" / "latest"
        written.extend(write_promotion_report(report, out_dir).values())
    if write_patch:
        out_dir = Path(report_dir) if report_dir else paths.reports_dir / "codegen" / "latest"
        profile_path = (
            context.suite_profile_path
            if context.suite_profile_path.exists()
            else context.module_profile_path
        )
        written.extend(write_promotion_patch(
            report,
            out_dir,
            profile_path=profile_path,
        ).values())
    if written:
        click.echo("Promotion artifacts written:")
        for path in written:
            click.echo(f"- {path}")
    return 0


def _dry_run_suite(context: SuiteContext) -> int:
    click.echo(f"Suite: {context.suite}")
    click.echo(f"Module: {context.module}")
    for path, parse_result in _parse_suite_files(context):
        skipped = [tc for tc in parse_result.cases if any("可行性存疑" in m for m in tc.markers)]
        manual = [tc for tc in parse_result.cases if any("manual" in m.lower() for m in tc.markers)]
        auto = [tc for tc in parse_result.cases if tc not in skipped and tc not in manual]
        click.echo(f"\n  {path.name}: {len(parse_result.cases)} cases")
        click.echo(f"    Auto:    {len(auto)}")
        click.echo(f"    Manual:  {len(manual)}")
        click.echo(f"    Skipped: {len(skipped)}")
        if parse_result.errors:
            click.echo("    Errors:")
            for err in parse_result.errors:
                click.echo(f"      {err}")
    click.echo("\n[dry-run] No files generated.")
    return 0


def _generate_suite(context: SuiteContext, paths: Any, project: ProjectConfig) -> int:
    click.echo(f"\n{'='*60}")
    click.echo(f"Suite: {context.suite}")
    click.echo(f"Module: {context.module}")
    click.echo(f"{'='*60}")
    blocked = 0
    generated = 0
    syntax_errors = 0
    for path, parse_result in _parse_suite_files(context):
        result = emit_file(
            parse_result,
            path.stem,
            profile_path=context.runtime_profile,
            output_dir=paths.generated_dir,
            fixture_dir=paths.profile_dir,
            project=project,
            output_file_type=_suite_output_file_type(context, path),
        )
        click.echo(f"\n  {result.output_path}")
        if result.diagnostics:
            blocked += 1
            click.echo("    Status:   BLOCKED")
            for diag in result.diagnostics:
                click.echo(f"      {diag}")
            continue
        generated += 1
        click.echo(f"    Cases:    {result.case_count}")
        click.echo(f"    Manual:   {result.manual_count}")
        click.echo(f"    Skipped:  {len(result.skipped)}")
        click.echo(f"    Unparsed: {len(result.unparsed)}")
        syntax_error = _ast_error(Path(result.output_path))
        if syntax_error:
            syntax_errors += 1
            click.echo("    Syntax:   ERROR")
            click.echo(f"      {syntax_error}")
        else:
            click.echo("    Syntax:   OK")

    click.echo(
        f"\nFinal summary: generated={generated}, "
        f"blocked={blocked}, syntax_errors={syntax_errors}"
    )
    return 1 if blocked or syntax_errors else 0


def _check_suite_consistency(
    context: SuiteContext,
    paths: Any,
    project: ProjectConfig,
) -> int:
    stale_count = 0
    blocked_count = 0
    target_files = {
        f"test_{context.module}_{_suite_output_file_type(context, path)}.py": path
        for path in context.case_files
    }
    for fname, source_path in sorted(target_files.items()):
        old_file = paths.generated_dir / fname
        existing_source = _generated_source_path(old_file)
        if existing_source and existing_source != str(source_path):
            click.echo(f"[CONFLICT] {fname} — generated from {existing_source}, not {source_path}")
            stale_count += 1

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        for path, parse_result in _parse_suite_files(context):
            result = emit_file(
                parse_result,
                path.stem,
                profile_path=context.runtime_profile,
                output_dir=tmp_path,
                fixture_dir=paths.profile_dir,
                project=project,
                output_file_type=_suite_output_file_type(context, path),
            )
            if result.diagnostics:
                click.echo(f"[BLOCKED] {Path(result.output_path).name}")
                for diag in result.diagnostics:
                    click.echo(f"  {diag}")
                blocked_count += 1
                stale_count += 1

        for fname in sorted(target_files):
            new_file = tmp_path / fname
            old_file = paths.generated_dir / fname
            syntax_error = _ast_error(new_file) if new_file.exists() else None
            if syntax_error:
                click.echo(f"[SYNTAX] {fname}")
                click.echo(f"  {syntax_error}")
                stale_count += 1
            if not old_file.exists():
                click.echo(f"[NEW] {fname} — not yet in generated/")
                stale_count += 1
                continue
            if not new_file.exists():
                continue
            old_lines = old_file.read_text(encoding="utf-8").splitlines(keepends=True)
            new_lines = new_file.read_text(encoding="utf-8").splitlines(keepends=True)
            diff = list(difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f"generated/{fname}",
                tofile=f"(regenerated) {fname}",
            ))
            if diff:
                click.echo(f"[STALE] {fname}")
                click.echo("".join(diff[:40]))
                stale_count += 1

    if stale_count:
        if blocked_count:
            click.echo(f"\n{blocked_count} file(s) blocked by diagnostics.")
        click.echo(f"\n{stale_count} file(s) stale. Run `aitest codegen --cases {context.suite_dir}` to update.")
        return 1
    click.echo("All generated files are up to date.")
    return 0


def _ast_error(path: Path) -> str | None:
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return f"{path}: {exc.msg} at line {exc.lineno}, column {exc.offset}"
    except FileNotFoundError:
        return None
    return None


def _generated_source_path(output_path: Path) -> str | None:
    if not output_path.exists():
        return None
    try:
        first_line = output_path.read_text(encoding="utf-8").splitlines()[0]
    except (IndexError, OSError, UnicodeDecodeError):
        return None
    prefix = "# Auto-generated from "
    return first_line[len(prefix):] if first_line.startswith(prefix) else None
