"""CLI-facing operations for legacy module-based codegen mode."""
from __future__ import annotations

import ast
import difflib
import json
import tempfile
from pathlib import Path
from typing import Any

import click
import yaml

from aitest_kit.codegen.emitter import emit_module
from aitest_kit.codegen.health import (
    build_codegen_health_report,
    codegen_health_to_dict,
    write_codegen_health_report,
)
from aitest_kit.codegen.ir import FileIR, ir_to_dict
from aitest_kit.codegen.parser import parse_case_file
from aitest_kit.codegen.planner import build_file_ir
from aitest_kit.codegen.project_config import load_project_config
from aitest_kit.codegen.promotion import (
    PromotionReport,
    analyze_case_body_promotion,
    promotion_to_dict,
    write_promotion_patch,
    write_promotion_report,
)
from aitest_kit.codegen.profile_validator import (
    validate_profile_module,
    write_profile_validation_report,
)


def list_modules(cases_dir: Path) -> list[str]:
    return sorted(
        d.name for d in cases_dir.iterdir()
        if d.is_dir()
        and not d.name.startswith(".")
        and ((d / "business.md").exists() or (d / "boundary.md").exists())
    )


def dump_ir(modules: list[str], paths: Any) -> int:
    payload = {
        "modules": [
            {
                "module": module,
                "files": [ir_to_dict(file_ir) for file_ir in _build_module_ir(module, paths)],
            }
            for module in modules
        ]
    }
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def explain_case(module: str, case_id: str, paths: Any) -> int:
    for file_ir in _build_module_ir(module, paths):
        for case_ir in file_ir.cases:
            if case_ir.case_id == case_id:
                click.echo(yaml.safe_dump(
                    ir_to_dict(case_ir),
                    allow_unicode=True,
                    sort_keys=False,
                ).rstrip())
                return 0
    click.echo(f"Case {case_id} not found in module {module}")
    return 1


def analyze_promotion(
    modules: list[str],
    paths: Any,
    *,
    output_dir: str | None = None,
    write_report: bool = False,
    write_patch: bool = False,
    echo_yaml: bool = True,
) -> int:
    report_dir = Path(output_dir) if output_dir else _default_codegen_report_dir(paths)
    reports = []
    written: list[Path] = []
    for module in modules:
        profile_path = _profile_path(module, paths)
        if profile_path is None:
            report = PromotionReport(module=module, total_case_bodies=0)
            item = promotion_to_dict(report)
            item["note"] = "codegen profile not found"
            reports.append(item)
            if write_report:
                written.extend(write_promotion_report(report, report_dir).values())
            if write_patch:
                written.extend(write_promotion_patch(report, report_dir).values())
            continue
        report = analyze_case_body_promotion(module, profile_path)
        reports.append(promotion_to_dict(report))
        if write_report:
            written.extend(write_promotion_report(report, report_dir).values())
        if write_patch:
            written.extend(write_promotion_patch(
                report,
                report_dir,
                profile_path=profile_path,
            ).values())

    if echo_yaml:
        click.echo(yaml.safe_dump(
            {"promotion_reports": reports},
            allow_unicode=True,
            sort_keys=False,
        ).rstrip())
    if written:
        click.echo("Promotion artifacts written:")
        for path in written:
            click.echo(f"- {path}")
    return 0


def validate_profiles(
    modules: list[str],
    paths: Any,
    *,
    output_dir: str | None = None,
    write_report: bool = False,
) -> int:
    report_dir = Path(output_dir) if output_dir else _default_codegen_report_dir(paths)
    project = load_project_config(paths.project_config)
    error_count = 0
    warning_count = 0
    written: list[Path] = []
    if not modules:
        click.echo("No modules found under the configured cases directory.")
        click.echo(
            "Next step: create "
            f"{paths.cases_dir}/<module>/business.md and a matching codegen profile "
            f"under {paths.profile_dir}."
        )
    for module in modules:
        report = validate_profile_module(
            module,
            cases_dir=paths.cases_dir,
            profile_dir=paths.profile_dir,
            project=project,
        )
        error_count += len(report.errors)
        warning_count += len(report.warnings)
        if write_report:
            written.extend(write_profile_validation_report(report, report_dir).values())
        click.echo(f"\nModule: {module}")
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
        f"\nProfile validation summary: modules={len(modules)}, "
        f"errors={error_count}, warnings={warning_count}"
    )
    if written:
        click.echo("Profile validation artifacts written:")
        for path in written:
            click.echo(f"- {path}")
    return 1 if error_count else 0


def profile_gate(modules: list[str], paths: Any) -> int:
    project = load_project_config(paths.project_config)
    reports = [
        validate_profile_module(
            module,
            cases_dir=paths.cases_dir,
            profile_dir=paths.profile_dir,
            project=project,
        )
        for module in modules
    ]
    error_count = sum(len(report.errors) for report in reports)
    if not error_count:
        return 0

    warning_count = sum(len(report.warnings) for report in reports)
    click.echo(
        f"Profile gate: modules={len(modules)}, "
        f"errors={error_count}, warnings={warning_count}"
    )
    click.echo("Profile gate blocked codegen:")
    for report in reports:
        if not report.errors:
            continue
        click.echo(f"\nModule: {report.module}")
        for diag in report.errors:
            click.echo(f"  {diag.format()}")
    click.echo("\nRun `aitest codegen --all --validate-profile --write-report` for artifacts.")
    return 1


def health_report(
    modules: list[str],
    paths: Any,
    *,
    output_dir: str | None = None,
    write_report: bool = False,
) -> int:
    project = load_project_config(paths.project_config)
    report = build_codegen_health_report(
        modules,
        paths.cases_dir,
        profile_dir=paths.profile_dir,
        project=project,
    )
    click.echo(yaml.safe_dump(
        codegen_health_to_dict(report),
        allow_unicode=True,
        sort_keys=False,
    ).rstrip())
    if write_report:
        report_dir = Path(output_dir) if output_dir else _default_codegen_report_dir(paths)
        written = write_codegen_health_report(report, report_dir)
        click.echo("Codegen health artifacts written:")
        for path in written.values():
            click.echo(f"- {path}")
    return 1 if report.error_count else 0


def check_consistency(
    modules: list[str],
    paths: Any,
    include_all_generated: bool = False,
    *,
    project=None,
) -> int:
    stale_count = 0
    blocked_count = 0
    target_files = _target_files(modules, paths)

    with tempfile.TemporaryDirectory() as tmpdir:
        for mod in modules:
            if not (paths.cases_dir / mod).exists():
                continue
            results = emit_module(
                mod,
                cases_dir=paths.cases_dir,
                output_dir=tmpdir,
                profile_dir=paths.profile_dir,
                project=project,
            )
            for result in results:
                if result.diagnostics:
                    click.echo(f"[BLOCKED] {Path(result.output_path).name}")
                    for diag in result.diagnostics:
                        click.echo(f"  {diag}")
                    blocked_count += 1
                    stale_count += 1

        stale_count += _compare_generated_files(
            Path(tmpdir),
            paths.generated_dir,
            target_files,
            include_all_generated,
        )

    if stale_count:
        if blocked_count:
            click.echo(f"\n{blocked_count} file(s) blocked by diagnostics.")
        click.echo(f"\n{stale_count} file(s) stale. Run `aitest codegen --all` to update.")
        return 1

    click.echo("All generated files are up to date.")
    return 0


def dry_run_modules(modules: list[str], paths: Any) -> None:
    for mod in modules:
        mod_dir = paths.cases_dir / mod
        if not mod_dir.exists():
            click.echo(f"[SKIP] {mod}: directory not found at {mod_dir}")
            continue
        click.echo(f"\n{'='*60}")
        click.echo(f"Module: {mod}")
        click.echo(f"{'='*60}")
        for md_file in ["business.md", "boundary.md"]:
            path = mod_dir / md_file
            if not path.exists():
                continue
            result = parse_case_file(path)
            skipped = [tc for tc in result.cases if any("可行性存疑" in m for m in tc.markers)]
            manual = [tc for tc in result.cases if any("manual" in m.lower() for m in tc.markers)]
            auto = [tc for tc in result.cases if tc not in skipped and tc not in manual]
            click.echo(f"\n  {md_file}: {len(result.cases)} cases")
            click.echo(f"    Auto:    {len(auto)}")
            click.echo(f"    Manual:  {len(manual)}")
            click.echo(f"    Skipped: {len(skipped)}")
            if result.errors:
                click.echo("    Errors:")
                for err in result.errors:
                    click.echo(f"      {err}")
            if skipped:
                for tc in skipped:
                    click.echo(f"      SKIP {tc.id}: {tc.markers}")
    click.echo("\n[dry-run] No files generated.")


def generate_modules(modules: list[str], paths: Any, project: Any) -> int:
    total_generated = 0
    total_blocked = 0
    total_syntax_errors = 0
    for mod in modules:
        generated, blocked, syntax_errors = _generate_one_module(mod, paths, project)
        total_generated += generated
        total_blocked += blocked
        total_syntax_errors += syntax_errors
    click.echo(
        f"\nFinal summary: generated={total_generated}, "
        f"blocked={total_blocked}, syntax_errors={total_syntax_errors}"
    )
    return 1 if total_blocked or total_syntax_errors else 0


def _generate_one_module(mod: str, paths: Any, project: Any) -> tuple[int, int, int]:
    mod_dir = paths.cases_dir / mod
    if not mod_dir.exists():
        click.echo(f"[SKIP] {mod}: directory not found at {mod_dir}")
        return 0, 0, 0
    click.echo(f"\n{'='*60}")
    click.echo(f"Module: {mod}")
    click.echo(f"{'='*60}")
    results = emit_module(
        mod,
        cases_dir=paths.cases_dir,
        output_dir=paths.generated_dir,
        profile_dir=paths.profile_dir,
        project=project,
    )
    generated = 0
    blocked = 0
    syntax_errors = 0
    for result in results:
        click.echo(f"\n  {result.output_path}")
        if result.diagnostics:
            blocked += 1
            click.echo("    Status:   BLOCKED")
            click.echo(f"    Diagnostics: {len(result.diagnostics)}")
            for diag in result.diagnostics:
                click.echo(f"      {diag}")
            continue
        generated += 1
        click.echo(f"    Cases:    {result.case_count}")
        click.echo(f"    Manual:   {result.manual_count}")
        click.echo(f"    Skipped:  {len(result.skipped)}")
        click.echo(f"    Unparsed: {len(result.unparsed)}")
        for tc_id, text in result.unparsed:
            click.echo(f"      {tc_id}: {text[:80]}")
        syntax_error = _ast_error(Path(result.output_path))
        if syntax_error:
            syntax_errors += 1
            click.echo("    Syntax:   ERROR")
            click.echo(f"      {syntax_error}")
        else:
            click.echo("    Syntax:   OK")
    click.echo(f"\n  Summary: generated={generated}, blocked={blocked}")
    return generated, blocked, syntax_errors


def _default_codegen_report_dir(paths: Any) -> Path:
    return paths.reports_dir / "codegen" / "latest"


def _profile_path(module: str, paths: Any) -> Path | None:
    path = paths.profile_dir / f"codegen_profile_{module}.md"
    return path if path.exists() else None


def _build_module_ir(module: str, paths: Any) -> list[FileIR]:
    project = load_project_config(paths.project_config)
    module_dir = paths.cases_dir / module
    profile_path = _profile_path(module, paths)
    files: list[FileIR] = []
    for file_type in ("business", "boundary"):
        md_path = module_dir / f"{file_type}.md"
        if not md_path.exists():
            continue
        parse_result = parse_case_file(md_path)
        files.append(build_file_ir(
            parse_result,
            file_type,
            profile_path=profile_path,
            project=project,
        ))
    return files


def _target_files(modules: list[str], paths: Any) -> set[str]:
    target_files: set[str] = set()
    for mod in modules:
        mod_dir = paths.cases_dir / mod
        for file_type in ("business", "boundary"):
            if (mod_dir / f"{file_type}.md").exists():
                target_files.add(f"test_{mod}_{file_type}.py")
    return target_files


def _compare_generated_files(
    tmp_path: Path,
    generated_dir: Path,
    target_files: set[str],
    include_all_generated: bool,
) -> int:
    stale_count = 0
    all_files = set()
    for file_path in tmp_path.glob("test_*.py"):
        all_files.add(file_path.name)
        syntax_error = _ast_error(file_path)
        if syntax_error:
            click.echo(f"[SYNTAX] {file_path.name}")
            click.echo(f"  {syntax_error}")
            stale_count += 1
    for file_path in generated_dir.glob("test_*.py"):
        if include_all_generated or file_path.name in target_files:
            all_files.add(file_path.name)

    for fname in sorted(all_files):
        new_file = tmp_path / fname
        old_file = generated_dir / fname
        if not old_file.exists():
            click.echo(f"[NEW] {fname} — not yet in generated/")
            stale_count += 1
            continue
        if not new_file.exists():
            click.echo(f"[EXTRA] {fname} — in generated/ but no source")
            stale_count += 1
            continue
        if _files_differ(old_file, new_file, fname):
            stale_count += 1
    return stale_count


def _files_differ(old_file: Path, new_file: Path, fname: str) -> bool:
    old_lines = old_file.read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines = new_file.read_text(encoding="utf-8").splitlines(keepends=True)
    diff = list(difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"generated/{fname}",
        tofile=f"(regenerated) {fname}",
    ))
    if not diff:
        return False
    click.echo(f"[STALE] {fname}")
    click.echo("".join(diff[:40]))
    return True


def _ast_error(path: Path) -> str | None:
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return f"{path}: {exc.msg} at line {exc.lineno}, column {exc.offset}"
    return None
