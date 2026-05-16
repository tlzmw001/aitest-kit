"""Workspace diagnostics for aitest-kit."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import click
import yaml

from aitest_kit.codegen.project_config import load_project_config
from aitest_kit.workspace import push_workspace


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
@click.option("--module", "module_name", help="Check one module instead of all discovered modules")
def doctor_command(workspace: str | None, module_name: str | None):
    """Diagnose workspace layout, codegen gates, and generated pytest collection."""
    try:
        with push_workspace(workspace):
            raise SystemExit(_doctor_impl(module_name))
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise click.ClickException(str(exc)) from exc


def _doctor_impl(module_name: str | None) -> int:
    workspace = Path.cwd()
    results: list[CheckResult] = []

    click.echo("AITest Doctor")
    click.echo(f"Workspace: {workspace}")
    click.echo("")

    _check_layout(results)
    _check_project_config(results)
    modules = _discover_modules(Path("test_workspace/cases"))
    selected_modules = _select_modules(modules, module_name, results)
    env_vars = _scan_env_vars(Path("test_workspace/tests/fixtures"))

    if selected_modules:
        _run_command_check(
            results,
            "profile gate",
            [sys.executable, "-m", "aitest_kit.cli", "codegen", *_module_args(selected_modules), "--validate-profile"],
        )
        _run_command_check(
            results,
            "generated freshness",
            [sys.executable, "-m", "aitest_kit.cli", "codegen", *_module_args(selected_modules), "--check"],
        )
    elif module_name is None:
        results.append(CheckResult(
            "WARN",
            "modules",
            "no modules found under test_workspace/cases",
        ))

    generated_files = _generated_files(selected_modules)
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
        Path("aitest_config/config.yaml"),
        Path("aitest_config/project_config.yaml"),
        Path("test_workspace/cases"),
        Path("test_workspace/tests/fixtures"),
        Path("test_workspace/tests/generated"),
    ]
    recommended = [
        Path("test_workspace/results"),
    ]
    missing_required = [str(path) for path in required if not path.exists()]
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
    config_path = Path("aitest_config/config.yaml")
    project_config_path = Path("aitest_config/project_config.yaml")
    try:
        if config_path.exists():
            yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        load_project_config(project_config_path)
    except Exception as exc:  # noqa: BLE001 - CLI diagnostic should report the concrete loader failure.
        results.append(CheckResult("FAIL", "project config", str(exc)))
        return
    results.append(CheckResult("OK", "project config", "config files load successfully"))


def _discover_modules(cases_dir: Path) -> list[str]:
    if not cases_dir.exists():
        return []
    return sorted(
        path.name for path in cases_dir.iterdir()
        if path.is_dir()
        and not path.name.startswith(".")
        and ((path / "business.md").exists() or (path / "boundary.md").exists())
    )


def _select_modules(
    modules: list[str],
    module_name: str | None,
    results: list[CheckResult],
) -> list[str]:
    if module_name is None:
        if modules:
            results.append(CheckResult(
                "OK",
                "modules",
                f"found {len(modules)} module(s): " + ", ".join(modules),
            ))
        return modules
    if module_name not in modules:
        results.append(CheckResult(
            "FAIL",
            "modules",
            f"module not found under test_workspace/cases: {module_name}",
        ))
        return []
    results.append(CheckResult("OK", "modules", f"found module: {module_name}"))
    return [module_name]


def _module_args(modules: list[str]) -> list[str]:
    if len(modules) == 1:
        return [modules[0]]
    return ["--all"]


def _run_command_check(
    results: list[CheckResult],
    name: str,
    command: list[str],
) -> None:
    completed = subprocess.run(command, text=True, capture_output=True)
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


def _generated_files(modules: list[str]) -> list[Path]:
    generated_dir = Path("test_workspace/tests/generated")
    if not generated_dir.exists():
        return []
    if not modules:
        return sorted(generated_dir.glob("test_*.py"))
    files: list[Path] = []
    for module in modules:
        for category in ("business", "boundary"):
            path = generated_dir / f"test_{module}_{category}.py"
            if path.exists():
                files.append(path)
    return files


def _scan_env_vars(fixture_dir: Path) -> set[str]:
    env_vars: set[str] = set()
    if not fixture_dir.exists():
        return env_vars
    for path in fixture_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in _ENV_PATTERNS:
            env_vars.update(pattern.findall(text))
    return env_vars
