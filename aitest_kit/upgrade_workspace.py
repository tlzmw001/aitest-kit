"""CLI command for safely upgrading an existing AITest workspace."""
from __future__ import annotations

from pathlib import Path

import click

from aitest_kit.workspace import upgrade_workspace


@click.command(name="upgrade")
@click.option(
    "--workspace",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    show_default=True,
    help="Existing AITest workspace root to upgrade.",
)
@click.option("--check", "check_only", is_flag=True, help="Report upgrade actions without writing files.")
@click.option("--apply", "apply_changes", is_flag=True, help="Apply safe template upgrades.")
@click.option(
    "--force-file",
    multiple=True,
    help="Overwrite one workspace-relative file even if it has local changes. Repeat as needed.",
)
def upgrade_command(
    workspace: Path,
    check_only: bool,
    apply_changes: bool,
    force_file: tuple[str, ...],
) -> None:
    """Upgrade template-managed files and report layout migration hints."""
    if check_only and apply_changes:
        raise click.ClickException("Use either --check or --apply, not both.")

    apply_mode = apply_changes
    try:
        result = upgrade_workspace(workspace, apply=apply_mode, force_files=set(force_file))
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise click.ClickException(str(exc)) from exc

    mode = "apply" if apply_mode else "check"
    click.echo("AITest Workspace Upgrade")
    click.echo(f"Workspace: {result.target}")
    click.echo(f"Mode: {mode}")
    click.echo("")

    for entry in result.entries:
        if entry.status == "OK":
            continue
        click.echo(f"[{entry.status}] {entry.relative.as_posix()} - {entry.message}")

    counts = result.counts()
    summary = ", ".join(f"{status.lower()}={counts[status]}" for status in sorted(counts))
    click.echo("")
    click.echo(f"Summary: {summary}")

    if apply_mode:
        click.echo(f"Applied: created={result.created}, updated={result.updated}, skipped={result.skipped}")
        if result.backup_dir is not None:
            click.echo(f"Backup: {result.backup_dir}")
    elif not any(entry.status != "OK" for entry in result.entries):
        click.echo("Workspace is up to date.")
