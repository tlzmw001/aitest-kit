"""Maintenance CLI for target/module/suite registries and task manifests."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import click
import yaml

from aitest_kit.registry.loader import load_module_context, load_suite_context, load_target_context
from aitest_kit.workspace import push_workspace


_TASK_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


@click.group(name="registry")
def registry_command() -> None:
    """Maintain target/module/suite registry wiring.

    \b
    Use registry commands when a suite should participate in:
      aitest codegen --target <target> --module <module>
      aitest run --target <target>
      aitest run --all

    Direct suite execution with --suite-file does not require registration.
    """


@registry_command.command(name="register-suite")
@click.option("--target", required=True, help="Target name that owns the module")
@click.option("--module", "module_name", required=True, help="Module name that owns the suite")
@click.option(
    "--suite-file",
    required=True,
    type=click.Path(file_okay=True, dir_okay=False),
    help="Path to the suite.yaml manifest to register",
)
@click.option("--status", default="active", show_default=True, help="Registered suite status")
@click.option("--dry-run", is_flag=True, help="Validate and print the planned change without writing")
@click.option("--workspace", type=click.Path(file_okay=False, dir_okay=True), help="Run from another AITest workspace root")
def register_suite_command(
    target: str,
    module_name: str,
    suite_file: str,
    status: str,
    dry_run: bool,
    workspace: str | None,
) -> None:
    """Register one suite under a target module.

    Registration is only needed for module/target/all aggregation. A suite can
    always be generated or run directly with --suite-file.

    \b
    Example:
      aitest registry register-suite --target <target> --module <module> --suite-file test_workspace/suites/<target>/<suite>/suite.yaml
    """
    with push_workspace(workspace):
        _register_suite_impl(
            target=target,
            module_name=module_name,
            suite_file=suite_file,
            status=status,
            dry_run=dry_run,
        )


@click.group(name="task")
def task_command() -> None:
    """Maintain task manifests.

    A task is an explicit execution list for suites that should run together.
    """


@task_command.command(name="create")
@click.option("--name", "task_name", required=True, help="Task name, used as the default filename")
@click.option(
    "--suite-file",
    "suite_files",
    multiple=True,
    required=True,
    type=click.Path(file_okay=True, dir_okay=False),
    help="Suite manifest to include in the task; repeat for multiple suites",
)
@click.option("--description", default="", help="Task description")
@click.option(
    "--output",
    type=click.Path(file_okay=True, dir_okay=False),
    help="Output task YAML path; defaults to test_workspace/tasks/<name>.yaml",
)
@click.option("--overwrite", is_flag=True, help="Overwrite an existing task file")
@click.option("--dry-run", is_flag=True, help="Validate and print the task YAML without writing")
@click.option("--workspace", type=click.Path(file_okay=False, dir_okay=True), help="Run from another AITest workspace root")
def task_create_command(
    task_name: str,
    suite_files: tuple[str, ...],
    description: str,
    output: str | None,
    overwrite: bool,
    dry_run: bool,
    workspace: str | None,
) -> None:
    """Create a task manifest from explicit suite files.

    A task does not discover suites automatically and does not require the
    suites to be registered under their modules.

    \b
    Example:
      aitest task create --name nightly_demo --suite-file path/to/a/suite.yaml --suite-file path/to/b/suite.yaml
    """
    with push_workspace(workspace):
        _task_create_impl(
            task_name=task_name,
            suite_files=suite_files,
            description=description,
            output=output,
            overwrite=overwrite,
            dry_run=dry_run,
        )


def _register_suite_impl(
    *,
    target: str,
    module_name: str,
    suite_file: str,
    status: str,
    dry_run: bool,
) -> None:
    status = status.strip()
    if not status:
        raise click.ClickException("--status must be non-empty")

    root = Path.cwd().resolve()
    target_context = load_target_context(target, workspace_root=root)
    _raise_diagnostics(target_context.diagnostics)

    module_context = load_module_context(target_context, module_name)
    _raise_diagnostics(module_context.diagnostics)
    if module_context.config_path is None:
        raise click.ClickException(f"module registry path is unavailable for {module_name}")

    suite_context = load_suite_context(_absolute_path(suite_file), workspace_root=root)
    _raise_diagnostics(suite_context.diagnostics)
    if suite_context.target != target_context.target:
        raise click.ClickException(
            f"suite target {suite_context.target} does not match target {target_context.target}"
        )
    if suite_context.module != module_context.module:
        raise click.ClickException(
            f"suite module {suite_context.module} does not match module {module_context.module}"
        )
    _validate_module_assets(module_context)
    _validate_suite_assets(suite_context)

    module_data = _read_yaml_mapping(module_context.config_path, "module")
    existing = module_data.get("registered_suites", [])
    if existing is None:
        existing = []
    if not isinstance(existing, list):
        raise click.ClickException("module registered_suites must be a list")

    manifest_value = _relative_to_workspace(suite_context.manifest_path, root)
    existing_index = _registered_suite_index(existing, suite_context.suite, root)
    changed = False
    desired_entry = {
        "suite": suite_context.suite,
        "manifest": manifest_value,
        "status": status,
    }
    if existing_index is None:
        existing.append(desired_entry)
        changed = True
    else:
        item = existing[existing_index]
        if isinstance(item, str):
            registered_manifest = _resolve_manifest_value(item, root)
            registered_status = "active"
        else:
            registered_manifest = _resolve_manifest_value(item.get("manifest"), root)
            registered_status = str(item.get("status", "active"))
        if registered_manifest != suite_context.manifest_path.resolve(strict=False):
            raise click.ClickException(
                "suite is already registered with a different manifest: "
                f"{item if isinstance(item, str) else item.get('manifest')}"
            )
        if not isinstance(item, dict) or item != desired_entry or registered_status != status:
            existing[existing_index] = desired_entry
            changed = True

    module_data["registered_suites"] = existing

    _print_registration_result(
        target=target_context.target,
        module=module_context.module,
        suite=suite_context.suite,
        manifest=manifest_value,
        status=status,
        changed=changed,
        dry_run=dry_run,
    )
    if dry_run:
        click.echo("\nPlanned module.yaml:")
        click.echo(_dump_yaml(module_data).rstrip())
        return
    if not changed:
        click.echo("Already registered; module registry unchanged.")
        return

    module_context.config_path.write_text(_dump_yaml(module_data), encoding="utf-8")
    reloaded = load_module_context(target_context, module_context.config_path)
    _raise_diagnostics(reloaded.diagnostics)
    click.echo(f"Updated: {_display_path(module_context.config_path)}")
    _print_register_next_steps(target_context.target, module_context.module)


def _task_create_impl(
    *,
    task_name: str,
    suite_files: tuple[str, ...],
    description: str,
    output: str | None,
    overwrite: bool,
    dry_run: bool,
) -> None:
    if not _TASK_NAME_RE.match(task_name):
        raise click.ClickException("task name may contain only letters, numbers, '_' and '-'")
    root = Path.cwd().resolve()
    output_path = _task_output_path(task_name, output, root)
    if output_path.exists() and not overwrite and not dry_run:
        raise click.ClickException(f"task file already exists: {_display_path(output_path)}")

    suites = [_load_valid_suite(path, root) for path in suite_files]
    units = [
        {
            "name": suite.suite,
            "suite_file": _relative_path(suite.manifest_path, output_path.parent),
        }
        for suite in suites
    ]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "task": task_name,
        "description": description,
        "units": units,
    }
    text = _dump_yaml(payload)

    click.echo(f"Task: {task_name}")
    click.echo(f"Suites: {len(units)}")
    click.echo(f"Output: {_display_path(output_path)}")
    if dry_run:
        click.echo("\nPlanned task.yaml:")
        click.echo(text.rstrip())
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    click.echo(f"Created: {_display_path(output_path)}")
    click.echo("\nNext:")
    click.echo(f"  aitest codegen --task-file {_display_path(output_path)} --check")
    click.echo(f"  aitest run --task-file {_display_path(output_path)}")


def _validate_module_assets(module_context: Any) -> None:
    if module_context.fixture_path is None:
        raise click.ClickException("module fixture.file is required before registering suites")
    if not module_context.fixture_path.exists():
        raise click.ClickException(f"module fixture not found: {module_context.fixture_path}")
    if module_context.profile_path is None or not module_context.profile_path.exists():
        raise click.ClickException(f"canonical module profile not found: {module_context.profile_path}")


def _validate_suite_assets(suite_context: Any) -> None:
    if suite_context.manifest_path is None or not suite_context.manifest_path.exists():
        raise click.ClickException("suite manifest not found")
    for case_file in suite_context.case_files:
        if not case_file.exists():
            raise click.ClickException(f"suite case file not found: {case_file}")
    if not suite_context.profile_path.exists():
        raise click.ClickException(f"suite profile not found: {suite_context.profile_path}")


def _load_valid_suite(suite_file: str, root: Path) -> Any:
    suite = load_suite_context(_absolute_path(suite_file), workspace_root=root)
    _raise_diagnostics(suite.diagnostics)
    _validate_suite_assets(suite)
    return suite


def _registered_suite_index(items: list[Any], suite_name: str, root: Path) -> int | None:
    for index, item in enumerate(items):
        if _registered_suite_name(item, root, index) == suite_name:
            return index
    return None


def _registered_suite_name(item: Any, root: Path, index: int) -> str:
    if isinstance(item, dict):
        suite = item.get("suite")
        if isinstance(suite, str) and suite.strip():
            return suite.strip()
        manifest = item.get("manifest")
    elif isinstance(item, str):
        manifest = item
    else:
        raise click.ClickException(
            f"registered_suites[{index}] must be a suite.yaml path string or a mapping"
        )

    suite_context = load_suite_context(_resolve_manifest_value(manifest, root), workspace_root=root)
    _raise_diagnostics(suite_context.diagnostics)
    return suite_context.suite


def _resolve_manifest_value(value: Any, root: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise click.ClickException("registered suite manifest must be a non-empty string")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve(strict=False)


def _task_output_path(task_name: str, output: str | None, root: Path) -> Path:
    path = Path(output).expanduser() if output else Path("test_workspace") / "tasks" / f"{task_name}.yaml"
    if not path.is_absolute():
        path = root / path
    return path.resolve(strict=False)


def _absolute_path(path_value: str) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve(strict=False)


def _relative_to_workspace(path: Path, root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root).as_posix()
    except ValueError:
        return path.resolve(strict=False).as_posix()


def _relative_path(path: Path, base_dir: Path) -> str:
    return Path(os.path.relpath(path.resolve(strict=False), base_dir.resolve(strict=False))).as_posix()


def _read_yaml_mapping(path: Path, label: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise click.ClickException(f"{label} YAML is invalid: {exc}") from exc
    if not isinstance(data, dict):
        raise click.ClickException(f"{label} YAML root must be a mapping")
    return data


def _dump_yaml(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def _raise_diagnostics(diagnostics: list[str]) -> None:
    if diagnostics:
        raise click.ClickException("; ".join(diagnostics))


def _display_path(path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.resolve(strict=False).as_posix()


def _print_registration_result(
    *,
    target: str,
    module: str,
    suite: str,
    manifest: str,
    status: str,
    changed: bool,
    dry_run: bool,
) -> None:
    click.echo("Suite registration:")
    click.echo(f"  target: {target}")
    click.echo(f"  module: {module}")
    click.echo(f"  suite: {suite}")
    click.echo(f"  manifest: {manifest}")
    click.echo(f"  status: {status}")
    click.echo(f"  changed: {str(changed).lower()}")
    if dry_run:
        click.echo("  mode: dry-run")


def _print_register_next_steps(target: str, module: str) -> None:
    click.echo("\nNext:")
    click.echo("  aitest doctor")
    click.echo(f"  aitest codegen --target {target} --module {module} --check")
