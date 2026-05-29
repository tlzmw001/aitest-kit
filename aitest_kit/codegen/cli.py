"""codegen CLI — parse and emit pytest from Markdown test cases."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import click
import yaml

from aitest_kit.codegen.module_runner import (
    analyze_promotion as run_analyze_promotion,
    check_consistency,
    dry_run_modules,
    dump_ir as dump_module_ir,
    explain_case,
    generate_modules,
    health_report as run_health_report,
    list_modules,
    profile_gate,
    validate_profiles,
)
from aitest_kit.codegen.project_config import load_project_config
from aitest_kit.codegen.suite_runner import run_suite_codegen
from aitest_kit.registry import load_task_context
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


@click.command()
@click.argument("module", required=False)
@click.option("--all", "all_modules", is_flag=True, help="Operate on all modules under test_workspace/cases")
@click.option("--cases", "cases_path", type=click.Path(file_okay=False, dir_okay=True), help="Operate on one case suite directory")
@click.option("--suite-file", type=click.Path(file_okay=True, dir_okay=False), help="Operate on one suite manifest file")
@click.option(
    "--task-file",
    "--task",
    "task_file",
    type=click.Path(file_okay=True, dir_okay=False),
    help="Operate on suites listed by one task manifest",
)
@click.option("--module", "module_option", help="Owning module for --cases when no aitest_suite.yaml is present")
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
    cases_path: str | None,
    suite_file: str | None,
    task_file: str | None,
    module_option: str | None,
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
                cases_path,
                suite_file,
                task_file,
                module_option,
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
    cases_path: str | None,
    suite_file: str | None,
    task_file: str | None,
    module_option: str | None,
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

    suite_sources = [item for item in (cases_path, suite_file, task_file) if item]
    if len(suite_sources) > 1:
        click.echo("Error: --cases, --suite-file, and --task-file are mutually exclusive")
        sys.exit(2)
    if (suite_file or task_file) and module_option:
        click.echo("Error: --module can only be used with --cases")
        sys.exit(2)
    if (suite_file or task_file) and (module or all_modules):
        click.echo("Error: --suite-file/--task-file cannot be combined with positional module or --all")
        sys.exit(2)

    if task_file:
        if dump_ir or explain or promotion_mode or health_report:
            click.echo(
                "Error: --task-file currently supports generation, --check, "
                "--dry-run, and --validate-profile"
            )
            sys.exit(2)
        sys.exit(_run_task_codegen(
            task_file,
            paths=paths,
            project=project,
            dry_run=dry_run,
            check=check,
            validate_profile=validate_profile,
            write_report=write_report,
            report_dir=report_dir,
        ))

    if cases_path or suite_file:
        suite_source = suite_file or cases_path
        if all_modules:
            click.echo("Error: --cases/--suite-file cannot be combined with --all")
            sys.exit(2)
        if module and module_option and module != module_option:
            click.echo("Error: positional module conflicts with --module")
            sys.exit(2)
        sys.exit(run_suite_codegen(
            suite_source,
            module_override=module_option or module,
            paths=paths,
            project=project,
            dry_run=dry_run,
            check=check,
            dump_ir=dump_ir,
            explain=explain,
            analyze_promotion=analyze_promotion,
            suggest_promotion_patch=suggest_promotion_patch,
            validate_profile=validate_profile,
            health_report=health_report,
            write_report=write_report,
            report_dir=report_dir,
        ))

    if all_modules:
        modules = list_modules(paths.cases_dir)
    elif module:
        modules = [module]
    else:
        click.echo("Usage: aitest codegen <module> or aitest codegen --all")
        sys.exit(1)

    if check:
        gate_result = profile_gate(modules, paths)
        if gate_result:
            sys.exit(gate_result)
        sys.exit(check_consistency(
            modules,
            paths,
            include_all_generated=all_modules,
            project=project,
        ))
    if validate_profile:
        sys.exit(validate_profiles(
            modules,
            paths,
            output_dir=report_dir,
            write_report=write_report,
        ))
    if health_report:
        sys.exit(run_health_report(
            modules,
            paths,
            output_dir=report_dir,
            write_report=write_report,
        ))
    if not dry_run:
        gate_result = profile_gate(modules, paths)
        if gate_result:
            sys.exit(gate_result)
    if dump_ir:
        sys.exit(dump_module_ir(modules, paths))
    if explain:
        if not module:
            click.echo("Error: --explain requires a module")
            sys.exit(2)
        sys.exit(explain_case(module, explain, paths))
    if promotion_mode:
        sys.exit(run_analyze_promotion(
            modules,
            paths,
            output_dir=report_dir,
            write_report=write_report or suggest_promotion_patch,
            write_patch=suggest_promotion_patch,
            echo_yaml=analyze_promotion,
        ))

    if dry_run:
        dry_run_modules(modules, paths)
        return
    sys.exit(generate_modules(modules, paths, project))


def _run_task_codegen(
    task_file: str,
    *,
    paths: CodegenPaths,
    project,
    dry_run: bool,
    check: bool,
    validate_profile: bool,
    write_report: bool,
    report_dir: str | None,
) -> int:
    task = load_task_context(task_file)
    if task.diagnostics:
        click.echo(f"Task: {task.task}")
        click.echo("Task manifest diagnostics:")
        for diagnostic in task.diagnostics:
            click.echo(f"  {diagnostic}")
        return 1
    if not task.units:
        click.echo(f"Task {task.task} has no units")
        return 1

    exit_code = 0
    click.echo(f"Task: {task.task}")
    for index, unit in enumerate(task.units, start=1):
        if unit.all:
            click.echo(f"\n[{index}] target all is not supported in Phase 2: {unit.target}")
            exit_code = 2
            continue
        if unit.suite_file is None:
            click.echo(f"\n[{index}] task unit requires suite_file in Phase 2")
            exit_code = 2
            continue
        click.echo(f"\n[{index}] suite_file: {unit.suite_file}")
        result = run_suite_codegen(
            str(unit.suite_file),
            module_override=unit.module or None,
            paths=paths,
            project=project,
            dry_run=dry_run,
            check=check,
            dump_ir=False,
            explain=None,
            analyze_promotion=False,
            suggest_promotion_patch=False,
            validate_profile=validate_profile,
            health_report=False,
            write_report=write_report,
            report_dir=report_dir,
        )
        if result:
            exit_code = result
    return exit_code
