"""codegen CLI — parse and emit pytest from Markdown test cases."""
from __future__ import annotations

import ast
import difflib
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

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
from aitest_kit.workspace import push_workspace


@dataclass(frozen=True)
class CodegenPaths:
    cases_dir: Path
    generated_dir: Path
    profile_dir: Path
    reports_dir: Path
    project_config: Path


def _load_codegen_paths() -> CodegenPaths:
    defaults = {
        "cases_dir": "test_workspace/cases",
        "generated_dir": "test_workspace/tests/generated",
        "fixtures_dir": "test_workspace/tests/fixtures",
        "reports_dir": "test_workspace/reports",
        "project_config": "aitest_config/project_config.yaml",
    }
    config_path = Path("aitest_config/config.yaml")
    if config_path.exists():
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        configured = cfg.get("paths", {}) if isinstance(cfg, dict) else {}
    else:
        configured = {}
    paths = {**defaults, **configured}
    return CodegenPaths(
        cases_dir=Path(paths["cases_dir"]),
        generated_dir=Path(paths["generated_dir"]),
        profile_dir=Path(paths["fixtures_dir"]),
        reports_dir=Path(paths["reports_dir"]),
        project_config=Path(paths["project_config"]),
    )


def _list_modules(cases_dir: Path) -> list[str]:
    return sorted(
        d.name for d in cases_dir.iterdir()
        if d.is_dir()
        and not d.name.startswith(".")
        and ((d / "business.md").exists() or (d / "boundary.md").exists())
    )


def _ast_error(path: Path) -> str | None:
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return f"{path}: {exc.msg} at line {exc.lineno}, column {exc.offset}"
    return None


def _profile_path(module: str, paths: CodegenPaths) -> Path | None:
    path = paths.profile_dir / f"codegen_profile_{module}.md"
    return path if path.exists() else None


def _build_module_ir(module: str, paths: CodegenPaths) -> list[FileIR]:
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


def _dump_ir(modules: list[str], paths: CodegenPaths) -> int:
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


def _explain_case(module: str, case_id: str, paths: CodegenPaths) -> int:
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


def _default_codegen_report_dir(paths: CodegenPaths) -> Path:
    return paths.reports_dir / "codegen" / "latest"


def _analyze_promotion(
    modules: list[str],
    paths: CodegenPaths,
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


def _validate_profiles(
    modules: list[str],
    paths: CodegenPaths,
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


def _profile_gate(modules: list[str], paths: CodegenPaths) -> int:
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


def _health_report(
    modules: list[str],
    paths: CodegenPaths,
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


def _check_consistency(
    modules: list[str],
    paths: CodegenPaths,
    include_all_generated: bool = False,
    *,
    project=None,
) -> int:
    generated_dir = paths.generated_dir
    stale_count = 0
    blocked_count = 0
    target_files: set[str] = set()
    for mod in modules:
        mod_dir = paths.cases_dir / mod
        for file_type in ("business", "boundary"):
            if (mod_dir / f"{file_type}.md").exists():
                target_files.add(f"test_{mod}_{file_type}.py")

    with tempfile.TemporaryDirectory() as tmpdir:
        for mod in modules:
            mod_dir = paths.cases_dir / mod
            if not mod_dir.exists():
                continue
            results = emit_module(
                mod,
                cases_dir=paths.cases_dir,
                output_dir=tmpdir,
                profile_dir=paths.profile_dir,
                project=project,
            )
            for r in results:
                if r.diagnostics:
                    click.echo(f"[BLOCKED] {Path(r.output_path).name}")
                    for diag in r.diagnostics:
                        click.echo(f"  {diag}")
                    blocked_count += 1
                    stale_count += 1

        tmp_path = Path(tmpdir)
        all_files = set()
        for f in tmp_path.glob("test_*.py"):
            all_files.add(f.name)
            syntax_error = _ast_error(f)
            if syntax_error:
                click.echo(f"[SYNTAX] {f.name}")
                click.echo(f"  {syntax_error}")
                stale_count += 1
        for f in generated_dir.glob("test_*.py"):
            if include_all_generated or f.name in target_files:
                all_files.add(f.name)

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

            old_lines = old_file.read_text(encoding="utf-8").splitlines(keepends=True)
            new_lines = new_file.read_text(encoding="utf-8").splitlines(keepends=True)
            diff = list(difflib.unified_diff(
                old_lines, new_lines,
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
        click.echo(f"\n{stale_count} file(s) stale. Run `aitest codegen --all` to update.")
        return 1

    click.echo("All generated files are up to date.")
    return 0


@click.command()
@click.argument("module", required=False)
@click.option("--all", "all_modules", is_flag=True, help="Operate on all modules under test_workspace/cases")
@click.option("--dry-run", is_flag=True, help="Parse Markdown only; do not write generated files")
@click.option("--check", is_flag=True, help="Verify generated pytest matches Markdown/profile/config")
@click.option("--dump-ir", is_flag=True, help="Print Case IR as JSON without generating files")
@click.option("--explain", metavar="TC_ID", help="Print Case IR explanation for one case")
@click.option("--analyze-promotion", is_flag=True, help="Analyze profile case_bodies promotion candidates")
@click.option("--write-report", is_flag=True, help="Write profile/health/promotion artifacts under reports/codegen")
@click.option("--suggest-promotion-patch", is_flag=True, help="Write review-only promotion patch artifacts")
@click.option("--report-dir", type=click.Path(file_okay=False, dir_okay=True), help="Codegen report output directory")
@click.option("--validate-profile", is_flag=True, help="Validate codegen_profile JSON Schema and semantics")
@click.option("--health-report", is_flag=True, help="Report codegen module health and maturity")
@click.option("--workspace", type=click.Path(file_okay=False, dir_okay=True), help="Run from another AITest workspace root")
def codegen(
    module: str | None,
    all_modules: bool,
    dry_run: bool,
    check: bool,
    dump_ir: bool,
    explain: str | None,
    analyze_promotion: bool,
    write_report: bool,
    suggest_promotion_patch: bool,
    report_dir: str | None,
    validate_profile: bool,
    health_report: bool,
    workspace: str | None,
):
    """Compile Markdown test cases into generated pytest files."""
    try:
        with push_workspace(workspace):
            _codegen_impl(
                module,
                all_modules,
                dry_run,
                check,
                dump_ir,
                explain,
                analyze_promotion,
                write_report,
                suggest_promotion_patch,
                report_dir,
                validate_profile,
                health_report,
            )
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise click.ClickException(str(exc)) from exc


def _codegen_impl(
    module: str | None,
    all_modules: bool,
    dry_run: bool,
    check: bool,
    dump_ir: bool,
    explain: str | None,
    analyze_promotion: bool,
    write_report: bool,
    suggest_promotion_patch: bool,
    report_dir: str | None,
    validate_profile: bool,
    health_report: bool,
) -> None:
    if check and dry_run:
        click.echo("Error: --check and --dry-run are mutually exclusive")
        sys.exit(2)
    promotion_mode = analyze_promotion or suggest_promotion_patch
    if (dump_ir or explain or promotion_mode or validate_profile or health_report) and (check or dry_run):
        click.echo("Error: report/IR/profile modes cannot be combined with --check or --dry-run")
        sys.exit(2)
    exclusive_modes = sum(bool(item) for item in [dump_ir, explain, promotion_mode, validate_profile, health_report])
    if exclusive_modes > 1:
        click.echo("Error: report/IR/profile modes are mutually exclusive")
        sys.exit(2)
    if explain and all_modules:
        click.echo("Error: --explain requires a single module, not --all")
        sys.exit(2)
    if write_report and not (promotion_mode or validate_profile or health_report):
        click.echo("Error: --write-report requires promotion analysis, --validate-profile, or --health-report")
        sys.exit(2)
    if report_dir and not (write_report or suggest_promotion_patch):
        click.echo("Error: --report-dir requires --write-report or --suggest-promotion-patch")
        sys.exit(2)

    paths = _load_codegen_paths()
    project = load_project_config(paths.project_config)

    if all_modules:
        modules = _list_modules(paths.cases_dir)
    elif module:
        modules = [module]
    else:
        click.echo("Usage: aitest codegen <module> or aitest codegen --all")
        sys.exit(1)

    if check:
        gate_result = _profile_gate(modules, paths)
        if gate_result:
            sys.exit(gate_result)
        sys.exit(_check_consistency(
            modules,
            paths,
            include_all_generated=all_modules,
            project=project,
        ))
    if validate_profile:
        sys.exit(_validate_profiles(
            modules,
            paths,
            output_dir=report_dir,
            write_report=write_report,
        ))
    if health_report:
        sys.exit(_health_report(
            modules,
            paths,
            output_dir=report_dir,
            write_report=write_report,
        ))
    if not dry_run:
        gate_result = _profile_gate(modules, paths)
        if gate_result:
            sys.exit(gate_result)
    if dump_ir:
        sys.exit(_dump_ir(modules, paths))
    if explain:
        if not module:
            click.echo("Error: --explain requires a module")
            sys.exit(2)
        sys.exit(_explain_case(module, explain, paths))
    if promotion_mode:
        sys.exit(_analyze_promotion(
            modules,
            paths,
            output_dir=report_dir,
            write_report=write_report or suggest_promotion_patch,
            write_patch=suggest_promotion_patch,
            echo_yaml=analyze_promotion,
        ))

    total_generated = 0
    total_blocked = 0
    total_syntax_errors = 0

    for mod in modules:
        mod_dir = paths.cases_dir / mod
        if not mod_dir.exists():
            click.echo(f"[SKIP] {mod}: directory not found at {mod_dir}")
            continue

        click.echo(f"\n{'='*60}")
        click.echo(f"Module: {mod}")
        click.echo(f"{'='*60}")

        if dry_run:
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
            continue

        results = emit_module(
            mod,
            cases_dir=paths.cases_dir,
            output_dir=paths.generated_dir,
            profile_dir=paths.profile_dir,
            project=project,
        )
        blocked = 0
        generated = 0
        syntax_errors = 0
        for r in results:
            click.echo(f"\n  {r.output_path}")
            if r.diagnostics:
                blocked += 1
                click.echo("    Status:   BLOCKED")
                click.echo(f"    Diagnostics: {len(r.diagnostics)}")
                for diag in r.diagnostics:
                    click.echo(f"      {diag}")
                continue

            generated += 1
            click.echo(f"    Cases:    {r.case_count}")
            click.echo(f"    Manual:   {r.manual_count}")
            click.echo(f"    Skipped:  {len(r.skipped)}")
            click.echo(f"    Unparsed: {len(r.unparsed)}")
            if r.unparsed:
                for tc_id, text in r.unparsed:
                    click.echo(f"      {tc_id}: {text[:80]}")
            syntax_error = _ast_error(Path(r.output_path))
            if syntax_error:
                syntax_errors += 1
                click.echo("    Syntax:   ERROR")
                click.echo(f"      {syntax_error}")
            else:
                click.echo("    Syntax:   OK")

        total_generated += generated
        total_blocked += blocked
        total_syntax_errors += syntax_errors
        click.echo(f"\n  Summary: generated={generated}, blocked={blocked}")

    if dry_run:
        click.echo("\n[dry-run] No files generated.")
    else:
        click.echo(
            f"\nFinal summary: generated={total_generated}, "
            f"blocked={total_blocked}, syntax_errors={total_syntax_errors}"
        )
        if total_blocked or total_syntax_errors:
            sys.exit(1)
