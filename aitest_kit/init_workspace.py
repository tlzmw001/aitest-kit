"""CLI command for creating a clean AITest workspace."""
from __future__ import annotations

from pathlib import Path

import click

from aitest_kit.workspace import init_workspace


@click.command(name="init")
@click.option(
    "--target",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    show_default=True,
    help="Directory where the AITest workspace skeleton will be created.",
)
@click.option("--force", is_flag=True, help="Overwrite template-managed workspace files if they already exist.")
def init_command(target: Path, force: bool) -> None:
    """Initialize a clean AITest workspace for one target system."""
    try:
        result = init_workspace(target, force=force)
    except FileExistsError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Workspace initialized: {result.target}")
    click.echo(f"Created: {result.created}, overwritten: {result.overwritten}")
    click.echo("")
    click.echo("Next steps:")
    click.echo(f"  cd {result.target}")
    click.echo("  aitest doctor")
    click.echo("  # after creating target/module/suite assets:")
    click.echo("  aitest codegen --suite-file <suite_dir>/suite.yaml --validate-profile")
