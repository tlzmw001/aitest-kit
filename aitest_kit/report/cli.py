"""CLI commands for test execution reporting."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import click
import yaml

from aitest_kit.report.collector import blocked_result, collect_result
from aitest_kit.report.renderer import render_markdown


def _load_paths() -> tuple[Path, Path]:
    config_path = Path("aitest_config/config.yaml")
    if config_path.exists():
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        paths = cfg.get("paths", {}) if isinstance(cfg, dict) else {}
        generated_dir = Path(paths.get("generated_dir", "test_workspace/tests/generated"))
        reports_dir = Path(paths.get("reports_dir", "test_workspace/reports"))
        return generated_dir, reports_dir
    return Path("test_workspace/tests/generated"), Path("test_workspace/reports")


@click.command(
    name="run",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.option("--include-manual", is_flag=True, help="Run tests marked manual")
@click.option("--skip-codegen-check", is_flag=True, help="Skip generated freshness check")
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def run_command(include_manual: bool, skip_codegen_check: bool, args: tuple[str, ...]):
    """Run generated pytest tests and write structured reports."""
    modules, extra_args = _split_args(args)
    generated_dir, reports_dir = _load_paths()
    files = _target_files(generated_dir, modules)
    run_id = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    run_dir = reports_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    command = "aitest run" + (" " + " ".join(modules) if modules else "")
    manual_policy = "included" if include_manual else "excluded"

    codegen_check = _codegen_check(modules, skip_codegen_check)
    if codegen_check["status"] == "failed":
        result = blocked_result(
            run_id=run_id,
            command=command,
            codegen_check=codegen_check,
            generated_files=files,
            manual_policy=manual_policy,
        )
        _write_result(run_dir, reports_dir, result)
        click.echo(f"BLOCKED_RUN: {codegen_check['message']}")
        raise SystemExit(10)

    if not files:
        result = collect_result(
            junit_path=None,
            generated_files=[],
            run_id=run_id,
            command=command,
            manual_policy=manual_policy,
            codegen_check=codegen_check,
            status="FAILED_RUN",
        )
        result["summary"]["error"] = 1
        _write_result(run_dir, reports_dir, result)
        click.echo("No generated test files found.")
        raise SystemExit(5)

    junit_path = run_dir / "junit.xml"
    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        *[str(path) for path in files],
        f"--junitxml={junit_path}",
        "-v",
    ]
    if not include_manual:
        pytest_cmd.extend(["-m", "not manual"])
    pytest_cmd.extend(extra_args)

    started = time.monotonic()
    completed = subprocess.run(pytest_cmd, text=True)
    duration = round(time.monotonic() - started, 3)

    result = collect_result(
        junit_path=junit_path,
        generated_files=files,
        run_id=run_id,
        command=command,
        duration_seconds=duration,
        manual_policy=manual_policy,
        codegen_check=codegen_check,
    )
    _write_result(run_dir, reports_dir, result)
    summary = result["summary"]
    click.echo(
        f"Report written: {run_dir / 'report.md'} "
        f"(passed={summary['passed']}, failed={summary['failed']}, error={summary['error']})"
    )
    raise SystemExit(completed.returncode)


@click.command(name="report")
@click.argument("run_id", required=False)
def report_command(run_id: str | None):
    """Re-render report.md from an existing result.json."""
    _, reports_dir = _load_paths()
    result_path = (
        reports_dir / "runs" / run_id / "result.json"
        if run_id
        else reports_dir / "latest" / "result.json"
    )
    if not result_path.exists():
        raise click.ClickException(f"result.json not found: {result_path}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    report_path = result_path.parent / "report.md"
    report_path.write_text(render_markdown(result), encoding="utf-8")
    click.echo(f"Report written: {report_path}")


def _split_args(args: tuple[str, ...]) -> tuple[list[str], list[str]]:
    modules: list[str] = []
    extra: list[str] = []
    in_extra = False
    for arg in args:
        if arg.startswith("-"):
            in_extra = True
        if in_extra:
            extra.append(arg)
        else:
            modules.append(arg)
    return modules, extra


def _target_files(generated_dir: Path, modules: list[str]) -> list[Path]:
    if not modules:
        return sorted(generated_dir.glob("test_*.py"))
    files: list[Path] = []
    for module in modules:
        for category in ("business", "boundary"):
            path = generated_dir / f"test_{module}_{category}.py"
            if path.exists():
                files.append(path)
    return files


def _codegen_check(modules: list[str], skip: bool) -> dict[str, str]:
    if skip:
        return {"status": "skipped", "command": "", "message": "--skip-codegen-check"}

    if not modules:
        cmd = [sys.executable, "-m", "aitest_kit.cli", "codegen", "--all", "--check"]
        completed = subprocess.run(cmd, text=True, capture_output=True)
        return _check_result(cmd, completed)

    messages: list[str] = []
    commands: list[str] = []
    for module in modules:
        cmd = [sys.executable, "-m", "aitest_kit.cli", "codegen", module, "--check"]
        commands.append(" ".join(cmd))
        completed = subprocess.run(cmd, text=True, capture_output=True)
        if completed.returncode:
            messages.append(completed.stdout + completed.stderr)
    if messages:
        return {"status": "failed", "command": " && ".join(commands), "message": "\n".join(messages).strip()}
    return {"status": "passed", "command": " && ".join(commands), "message": ""}


def _check_result(cmd: list[str], completed: subprocess.CompletedProcess[str]) -> dict[str, str]:
    status = "passed" if completed.returncode == 0 else "failed"
    return {
        "status": status,
        "command": " ".join(cmd),
        "message": (completed.stdout + completed.stderr).strip(),
    }


def _write_result(run_dir: Path, reports_dir: Path, result: dict) -> None:
    result_path = run_dir / "result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "report.md").write_text(render_markdown(result), encoding="utf-8")

    latest_dir = reports_dir / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(run_dir, latest_dir)

