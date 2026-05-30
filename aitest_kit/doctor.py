"""Workspace diagnostics for aitest-kit."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import click

from aitest_kit.codegen.project_config import load_project_config
from aitest_kit.codegen.profile_validator import validate_profile_suite
from aitest_kit.registry import load_module_context, load_suite_context, load_target_context
from aitest_kit.workspace import push_workspace
from aitest_kit.workspace_config import has_workspace_config, load_workspace_paths


_ENV_PATTERNS = [
    re.compile(r"os\.environ\.get\(\s*[\"']([A-Z0-9_]+)[\"']"),
    re.compile(r"os\.getenv\(\s*[\"']([A-Z0-9_]+)[\"']"),
]


@dataclass
class CheckResult:
    level: str
    name: str
    message: str


@click.command(name="doctor")
@click.option("--workspace", type=click.Path(file_okay=False, dir_okay=True), help="Check another AITest workspace root")
def doctor_command(workspace: str | None):
    """Diagnose workspace layout, registries, codegen gates, and pytest collection.

    \b
    Checks:
      workspace layout
      project config
      target/module/suite registry
      profile gate
      generated freshness
      pytest collect
      fixture environment variable hints
    """
    try:
        with push_workspace(workspace):
            raise SystemExit(_doctor_impl())
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise click.ClickException(str(exc)) from exc


def _doctor_impl() -> int:
    workspace = Path.cwd()
    results: list[CheckResult] = []

    click.echo("AITest Doctor")
    click.echo(f"Workspace: {workspace}")
    click.echo("")

    _check_layout(results)
    _check_project_config(results)
    paths = load_workspace_paths()
    suite_dirs = _discover_case_suites(Path("test_workspace/suites"))
    env_vars = _scan_env_vars(Path("test_workspace/targets"))
    _check_case_suites(results, suite_dirs, paths.profile_dir)
    _check_target_registry(results, Path("test_workspace/targets"))

    if suite_dirs:
        _run_suite_codegen_checks(
            results,
            "profile gate",
            suite_dirs,
            "--validate-profile",
        )
        _run_suite_codegen_checks(
            results,
            "generated freshness",
            suite_dirs,
            "--check",
        )
    else:
        results.append(CheckResult(
            "WARN",
            "case suites",
            "no suite.yaml files found under test_workspace/suites",
        ))

    generated_files = _generated_files(paths.generated_dir)
    if generated_files:
        _run_command_check(
            results,
            "pytest collect",
            [sys.executable, "-m", "pytest", *[str(path) for path in generated_files], "--collect-only", "-q"],
        )
    else:
        results.append(CheckResult(
            "WARN",
            "pytest collect",
            "no generated pytest files found",
        ))

    if env_vars:
        results.append(CheckResult(
            "INFO",
            "environment",
            "fixture environment variables: " + ", ".join(sorted(env_vars)),
        ))
    else:
        results.append(CheckResult(
            "INFO",
            "environment",
            "no fixture environment variables detected",
        ))

    counts = {"OK": 0, "WARN": 0, "FAIL": 0, "INFO": 0}
    for result in results:
        counts[result.level] += 1
        click.echo(f"[{result.level}] {result.name}: {result.message}")

    click.echo("")
    click.echo(
        "Summary: "
        f"ok={counts['OK']}, warn={counts['WARN']}, "
        f"fail={counts['FAIL']}, info={counts['INFO']}"
    )
    return 1 if counts["FAIL"] else 0


def _check_layout(results: list[CheckResult]) -> None:
    required = [
        Path("test_workspace/targets"),
        Path("test_workspace/suites"),
        Path("test_workspace/generated"),
    ]
    recommended = [
        Path("test_workspace/results"),
    ]
    missing_required = [str(path) for path in required if not path.exists()]
    if not has_workspace_config():
        missing_required.append("aitest_config/aitest.yaml")
    missing_recommended = [str(path) for path in recommended if not path.exists()]
    if missing_required:
        results.append(CheckResult(
            "FAIL",
            "workspace layout",
            "missing required path(s): " + ", ".join(missing_required),
        ))
        return
    if missing_recommended:
        results.append(CheckResult(
            "WARN",
            "workspace layout",
            "missing recommended path(s): " + ", ".join(missing_recommended),
        ))
        return
    results.append(CheckResult("OK", "workspace layout", "required paths exist"))


def _check_project_config(results: list[CheckResult]) -> None:
    try:
        paths = load_workspace_paths()
        load_project_config(paths.project_config)
    except Exception as exc:  # noqa: BLE001 - CLI diagnostic should report the concrete loader failure.
        results.append(CheckResult("FAIL", "project config", str(exc)))
        return
    results.append(CheckResult("OK", "project config", "config files load successfully"))


def _check_case_suites(
    results: list[CheckResult],
    suite_dirs: list[Path],
    profile_dir: Path,
) -> None:
    if not suite_dirs:
        return
    try:
        project = load_project_config(load_workspace_paths().project_config)
    except Exception as exc:  # noqa: BLE001 - doctor should surface loader failures.
        results.append(CheckResult("FAIL", "case suites", str(exc)))
        return

    failures: list[str] = []
    warnings: list[str] = []
    for suite_dir in suite_dirs:
        manifest = suite_dir / "suite.yaml"
        report = validate_profile_suite(manifest, profile_dir=profile_dir, project=project)
        if report.errors:
            first = report.errors[0].format()
            failures.append(f"{suite_dir}: {len(report.errors)} error(s), first={first}")
        elif report.warnings:
            warnings.append(f"{suite_dir}: {len(report.warnings)} warning(s)")

    if failures:
        results.append(CheckResult("FAIL", "case suites", "; ".join(failures)))
    elif warnings:
        results.append(CheckResult("WARN", "case suites", "; ".join(warnings)))
    else:
        results.append(CheckResult("OK", "case suites", f"{len(suite_dirs)} suite(s) valid"))


def _discover_case_suites(suites_dir: Path) -> list[Path]:
    if not suites_dir.exists():
        return []
    return sorted(path.parent for path in suites_dir.rglob("suite.yaml"))


def _check_target_registry(results: list[CheckResult], targets_dir: Path) -> None:
    target_files = sorted(targets_dir.glob("*/target.yaml"))
    if not target_files:
        results.append(CheckResult("INFO", "target registry", "no target registry entries found"))
        return

    failures: list[str] = []
    warnings: list[str] = []
    module_count = 0
    suite_count = 0
    for target_file in target_files:
        target = load_target_context(target_file)
        if target.diagnostics:
            failures.append(f"{target_file}: {_diagnostic_summary(target.diagnostics)}")
            continue
        if not target.defaults.module_dir.exists():
            warnings.append(f"{target.target}: module_dir not found: {target.defaults.module_dir}")
            continue
        module_files = sorted(target.defaults.module_dir.glob("*.yaml"))
        if not module_files:
            warnings.append(f"{target.target}: no module registry files under {target.defaults.module_dir}")
            continue
        for module_file in module_files:
            module_count += 1
            module = load_module_context(target, module_file)
            if module.diagnostics:
                failures.append(f"{module_file}: {_diagnostic_summary(module.diagnostics)}")
                continue
            if module.fixture_path and not module.fixture_path.exists():
                failures.append(f"{module_file}: fixture not found: {module.fixture_path}")
            if module.profile_path and not module.profile_path.exists():
                failures.append(f"{module_file}: profile not found: {module.profile_path}")
            for registered in module.registered_suites:
                suite_count += 1
                if registered.status != "active":
                    continue
                if not registered.manifest.exists():
                    failures.append(f"{module_file}: suite manifest not found: {registered.manifest}")
                    continue
                suite = load_suite_context(registered.manifest)
                if suite.diagnostics:
                    failures.append(f"{registered.manifest}: {_diagnostic_summary(suite.diagnostics)}")
                    continue
                if suite.target != target.target or suite.module != module.module:
                    failures.append(
                        f"{registered.manifest}: suite target/module "
                        f"{suite.target}/{suite.module} does not match "
                        f"{target.target}/{module.module}"
                    )
                for case_file in suite.case_files:
                    if not case_file.exists():
                        failures.append(f"{registered.manifest}: case file not found: {case_file}")
                if not suite.profile_path.exists():
                    failures.append(f"{registered.manifest}: suite profile not found: {suite.profile_path}")

    if failures:
        results.append(CheckResult("FAIL", "target registry", "; ".join(failures[:4])))
    elif warnings:
        results.append(CheckResult("WARN", "target registry", "; ".join(warnings[:4])))
    else:
        results.append(CheckResult(
            "OK",
            "target registry",
            f"{len(target_files)} target(s), {module_count} module(s), {suite_count} registered suite(s) valid",
        ))


def _diagnostic_summary(diagnostics: list[str]) -> str:
    return "; ".join(diagnostics[:3])


def _run_command_check(
    results: list[CheckResult],
    name: str,
    command: list[str],
) -> None:
    env = dict(os.environ)
    package_root = str(Path(__file__).resolve().parents[1])
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        package_root if not existing_pythonpath
        else package_root + os.pathsep + existing_pythonpath
    )
    completed = subprocess.run(command, text=True, capture_output=True, env=env)
    if completed.returncode == 0:
        results.append(CheckResult("OK", name, "passed"))
        return
    output = (completed.stdout + completed.stderr).strip()
    if len(output) > 500:
        output = output[:500].rstrip() + " ..."
    results.append(CheckResult(
        "FAIL",
        name,
        output or f"command failed: {' '.join(command)}",
    ))


def _run_suite_codegen_checks(
    results: list[CheckResult],
    name: str,
    suite_dirs: list[Path],
    mode: str,
) -> None:
    failures: list[str] = []
    for suite_dir in suite_dirs:
        manifest = suite_dir / "suite.yaml"
        command = [
            sys.executable,
            "-m",
            "aitest_kit.cli",
            "codegen",
            "--suite-file",
            str(manifest),
            mode,
        ]
        env = dict(os.environ)
        package_root = str(Path(__file__).resolve().parents[1])
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            package_root if not existing_pythonpath
            else package_root + os.pathsep + existing_pythonpath
        )
        completed = subprocess.run(command, text=True, capture_output=True, env=env)
        if completed.returncode:
            output = (completed.stdout + completed.stderr).strip()
            if len(output) > 300:
                output = output[:300].rstrip() + " ..."
            failures.append(f"{manifest}: {output or 'failed'}")
    if failures:
        results.append(CheckResult("FAIL", name, "; ".join(failures[:3])))
    else:
        results.append(CheckResult("OK", name, f"{len(suite_dirs)} suite(s) passed"))


def _generated_files(generated_dir: Path) -> list[Path]:
    if not generated_dir.exists():
        return []
    return sorted(generated_dir.rglob("test_*.py"))


def _scan_env_vars(fixture_dir: Path) -> set[str]:
    env_vars: set[str] = set()
    if not fixture_dir.exists():
        return env_vars
    for path in fixture_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in _ENV_PATTERNS:
            env_vars.update(pattern.findall(text))
    return env_vars
