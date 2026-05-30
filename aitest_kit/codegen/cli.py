"""codegen CLI — parse and emit pytest from Markdown test cases."""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import click
import yaml

from aitest_kit.codegen.health import (
    CodegenHealthReport,
    build_suite_codegen_health_report,
    codegen_health_to_dict,
    write_codegen_health_report,
)
from aitest_kit.codegen.promotion import (
    PromotionReport,
    analyze_case_body_promotion,
    promotion_to_dict,
    write_promotion_report,
)
from aitest_kit.codegen.project_config import load_project_config
from aitest_kit.codegen.profile_validator import validate_profile_suite
from aitest_kit.codegen.suite import (
    SuiteContext,
    load_suite_context_for_paths,
    parse_suite_case_file,
    resolve_suite_runtime_paths,
)
from aitest_kit.codegen.suite_runner import run_suite_codegen
from aitest_kit.codegen.suite_target import project_config_for_suite_target
from aitest_kit.registry import load_task_context
from aitest_kit.registry.models import TaskContext, TaskUnit
from aitest_kit.registry.selection import build_task_context_from_selectors
from aitest_kit.workspace import push_workspace
from aitest_kit.workspace_config import load_workspace_paths


@dataclass(frozen=True)
class CodegenPaths:
    generated_dir: Path
    profile_dir: Path
    reports_dir: Path
    project_config: Path


def _load_codegen_paths() -> CodegenPaths:
    paths = load_workspace_paths()
    return CodegenPaths(
        generated_dir=paths.generated_dir,
        profile_dir=paths.profile_dir,
        reports_dir=paths.reports_dir,
        project_config=paths.project_config,
    )


@click.command()
@click.option("--suite-file", type=click.Path(file_okay=True, dir_okay=False), help="Operate on one suite manifest file")
@click.option(
    "--task-file",
    "--task",
    "task_file",
    type=click.Path(file_okay=True, dir_okay=False),
    help="Operate on suites listed by one task manifest",
)
@click.option("--target", help="Operate on active suites registered under one target")
@click.option("--module", "module_name", help="Operate on active suites registered under one module")
@click.option("--all", "all_suites", is_flag=True, help="Operate on all active suites in the registry")
@click.option("--dry-run", is_flag=True, help="Parse Markdown only; do not write generated files")
@click.option("--check", is_flag=True, help="Verify generated pytest matches Markdown/profile/config")
@click.option("--dump-ir", is_flag=True, help="Print Case IR as JSON without generating files")
@click.option("--explain", metavar="TC_ID", help="Print Case IR explanation for one case")
@click.option("--analyze-promotion", is_flag=True, help="Analyze profile case_bodies promotion candidates")
@click.option("--write-report", is_flag=True, help="Write profile/health/promotion artifacts under reports/codegen")
@click.option("--suggest-promotion-patch", is_flag=True, help="Write review-only promotion patch artifacts")
@click.option("--report-dir", type=click.Path(file_okay=False, dir_okay=True), help="Codegen report output directory")
@click.option("--validate-profile", is_flag=True, help="Validate codegen_profile JSON Schema and semantics")
@click.option("--health-report", is_flag=True, help="Report codegen suite health and maturity")
@click.option("--workspace", type=click.Path(file_okay=False, dir_okay=True), help="Run from another AITest workspace root")
def codegen(
    suite_file: str | None,
    task_file: str | None,
    target: str | None,
    module_name: str | None,
    all_suites: bool,
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
    """Compile Markdown test suites/tasks into generated pytest files.

    \b
    Typical suite flow:
      aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --validate-profile
      aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --dump-ir
      aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
      aitest codegen --suite-file test_workspace/suites/<target>/<suite>/suite.yaml --check

    \b
    Selector flow:
      aitest codegen --target <target> --module <module> --check
      aitest codegen --target <target> --check
      aitest codegen --task-file test_workspace/tasks/<task>.yaml --check

    \b
    Notes:
      --dry-run parses Markdown only.
      --dump-ir and --explain are suite-level diagnosis tools.
      --check never writes generated pytest.
    """
    try:
        with push_workspace(workspace):
            _codegen_impl(
                suite_file,
                task_file,
                target,
                module_name,
                all_suites,
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
    suite_file: str | None,
    task_file: str | None,
    target: str | None,
    module_name: str | None,
    all_suites: bool,
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
    if write_report and not (promotion_mode or validate_profile or health_report):
        click.echo("Error: --write-report requires promotion analysis, --validate-profile, or --health-report")
        sys.exit(2)
    if report_dir and not (write_report or suggest_promotion_patch):
        click.echo("Error: --report-dir requires --write-report or --suggest-promotion-patch")
        sys.exit(2)

    paths = _load_codegen_paths()
    project = load_project_config(paths.project_config)

    if suite_file and task_file:
        click.echo("Error: --suite-file and --task-file are mutually exclusive")
        sys.exit(2)
    selector_used = bool(target or module_name or all_suites)
    if selector_used and (suite_file or task_file):
        click.echo("Error: target/module/all selectors cannot be combined with --suite-file or --task-file")
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

    if selector_used:
        if dump_ir or explain or suggest_promotion_patch:
            click.echo(
                "Error: target/module/all selectors currently support generation, "
                "--check, --dry-run, --validate-profile, module/target "
                "--health-report, and module/target --analyze-promotion"
            )
            sys.exit(2)
        if all_suites and (analyze_promotion or health_report):
            click.echo("Error: --all does not support --health-report or --analyze-promotion; use --target or --module")
            sys.exit(2)
        task, diagnostics = build_task_context_from_selectors(
            target=target or "",
            module=module_name or "",
            all_suites=all_suites,
        )
        if diagnostics or task is None:
            for diagnostic in diagnostics:
                click.echo(diagnostic)
            sys.exit(2)
        if analyze_promotion:
            sys.exit(_run_task_context_promotion(
                task,
                paths=paths,
                project=project,
                write_report=write_report,
                report_dir=report_dir,
            ))
        if health_report:
            sys.exit(_run_task_context_health(
                task,
                paths=paths,
                project=project,
                write_report=write_report,
                report_dir=report_dir,
            ))
        sys.exit(_run_task_context_codegen(
            task,
            paths=paths,
            project=project,
            dry_run=dry_run,
            check=check,
            validate_profile=validate_profile,
            write_report=write_report,
            report_dir=report_dir,
        ))

    if suite_file:
        sys.exit(run_suite_codegen(
            suite_file,
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

    click.echo(
        "Usage: aitest codegen --suite-file <suite.yaml>, "
        "--task-file <task.yaml>, --target <target> [--module <module>], or --all"
    )
    sys.exit(1)


def _suite_context_for_task_unit(
    unit: TaskUnit,
    *,
    paths: CodegenPaths,
    project,
) -> tuple[SuiteContext, object, object]:
    if unit.suite_file is None:
        raise ValueError("task unit requires suite_file")
    context = load_suite_context_for_paths(
        unit.suite_file,
        profile_dir=paths.profile_dir,
    )
    runtime_paths = resolve_suite_runtime_paths(
        context,
        generated_dir=paths.generated_dir,
        reports_dir=paths.reports_dir,
        profile_dir=paths.profile_dir,
    )
    suite_project = project_config_for_suite_target(context, project)
    return context, runtime_paths, suite_project


def _profile_gate_for_suite(context: SuiteContext, runtime_paths: object, project) -> list[str]:
    report = validate_profile_suite(
        context.manifest_path or context.suite_dir,
        profile_dir=runtime_paths.profile_dir,
        project=project,
    )
    return [diag.format() for diag in report.errors]


def _run_task_context_health(
    task: TaskContext,
    *,
    paths: CodegenPaths,
    project,
    write_report: bool,
    report_dir: str | None,
) -> int:
    if task.diagnostics:
        for diagnostic in task.diagnostics:
            click.echo(diagnostic)
        return 1
    suite_reports = []
    for unit in task.units:
        context, runtime_paths, suite_project = _suite_context_for_task_unit(unit, paths=paths, project=project)
        errors = _profile_gate_for_suite(context, runtime_paths, suite_project)
        if errors:
            click.echo(f"Profile gate blocked health report for suite {context.suite}:")
            for error in errors:
                click.echo(f"  {error}")
            return 1
        suite_reports.append(build_suite_codegen_health_report(context, project=suite_project))

    combined = CodegenHealthReport([
        module
        for report in suite_reports
        for module in report.modules
    ])
    click.echo(yaml.safe_dump(
        codegen_health_to_dict(combined),
        allow_unicode=True,
        sort_keys=False,
    ).rstrip())
    if write_report:
        out_dir = Path(report_dir) if report_dir else paths.reports_dir / "codegen" / "latest"
        written = write_codegen_health_report(combined, out_dir)
        click.echo("Codegen health artifacts written:")
        for path in written.values():
            click.echo(f"- {path}")
    return 1 if combined.error_count else 0


def _run_task_context_promotion(
    task: TaskContext,
    *,
    paths: CodegenPaths,
    project,
    write_report: bool,
    report_dir: str | None,
) -> int:
    if task.diagnostics:
        for diagnostic in task.diagnostics:
            click.echo(diagnostic)
        return 1
    reports: list[PromotionReport] = []
    for unit in task.units:
        context, runtime_paths, suite_project = _suite_context_for_task_unit(unit, paths=paths, project=project)
        errors = _profile_gate_for_suite(context, runtime_paths, suite_project)
        if errors:
            click.echo(f"Profile gate blocked promotion analysis for suite {context.suite}:")
            for error in errors:
                click.echo(f"  {error}")
            return 1
        case_ids = {
            tc.id
            for case_file in context.case_files
            for tc in parse_suite_case_file(case_file, context.module).cases
        }
        reports.append(analyze_case_body_promotion(
            context.module,
            context.runtime_profile,
            suite=context.suite,
            case_ids=case_ids,
        ))

    payload = _promotion_aggregate_to_dict(task, reports)
    click.echo(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False).rstrip())
    if write_report:
        out_dir = Path(report_dir) if report_dir else paths.reports_dir / "codegen" / "latest"
        written = _write_promotion_aggregate(task, reports, out_dir)
        click.echo("Promotion artifacts written:")
        for path in written:
            click.echo(f"- {path}")
    return 0


def _promotion_aggregate_to_dict(task: TaskContext, reports: list[PromotionReport]) -> dict:
    return {
        "promotion_summary": {
            "task": task.task,
            "suite_count": len(reports),
            "total_case_bodies": sum(report.total_case_bodies for report in reports),
            "candidate_groups": sum(1 for report in reports for group in report.groups if group.candidate),
        },
        "promotion_reports": [promotion_to_dict(report) for report in reports],
    }


def _write_promotion_aggregate(task: TaskContext, reports: list[PromotionReport], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = _promotion_aggregate_to_dict(task, reports)
    summary_base = output_dir / f"{_safe_artifact_name(task.task)}_promotion_summary"
    summary_md = summary_base.with_suffix(".md")
    summary_json = summary_base.with_suffix(".json")
    summary_md.write_text(_render_promotion_summary_markdown(task, reports) + "\n", encoding="utf-8")
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    written = [summary_md, summary_json]
    for report in reports:
        suite_dir = output_dir / "suites" / _safe_artifact_name(report.suite or report.module)
        written.extend(write_promotion_report(report, suite_dir).values())
    return written


def _render_promotion_summary_markdown(task: TaskContext, reports: list[PromotionReport]) -> str:
    lines = [
        f"# Codegen Promotion Summary: {task.task}",
        "",
        f"- **Suites**: {len(reports)}",
        f"- **Total case_bodies**: {sum(report.total_case_bodies for report in reports)}",
        f"- **Candidate groups**: {sum(1 for report in reports for group in report.groups if group.candidate)}",
        "",
        "| Module | Suite | case_bodies | candidate groups |",
        "|---|---|---:|---:|",
    ]
    for report in reports:
        candidate_count = sum(1 for group in report.groups if group.candidate)
        lines.append(
            f"| `{report.module}` | `{report.suite or '-'}` | "
            f"{report.total_case_bodies} | {candidate_count} |"
        )
    return "\n".join(lines)


def _safe_artifact_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_") or "selected"


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
    return _run_task_context_codegen(
        task,
        paths=paths,
        project=project,
        dry_run=dry_run,
        check=check,
        validate_profile=validate_profile,
        write_report=write_report,
        report_dir=report_dir,
    )


def _run_task_context_codegen(
    task: TaskContext,
    *,
    paths: CodegenPaths,
    project,
    dry_run: bool,
    check: bool,
    validate_profile: bool,
    write_report: bool,
    report_dir: str | None,
) -> int:
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
        if unit.suite_file is None:
            click.echo(f"\n[{index}] task unit requires suite_file")
            exit_code = 2
            continue
        click.echo(f"\n[{index}] suite_file: {unit.suite_file}")
        result = run_suite_codegen(
            str(unit.suite_file),
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
