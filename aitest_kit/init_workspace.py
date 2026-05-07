"""CLI command for initializing a clean AITest project workspace."""
from __future__ import annotations

from pathlib import Path

import click

from aitest_kit.workspace import init_workspace


@click.command(name="init")
@click.option(
    "--target",
    default=".",
    show_default=True,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    help="Project directory where the AITest workspace template will be copied.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing template-managed files in the target directory.",
)
def init_command(target: Path, force: bool) -> None:
    """Initialize a clean project workspace from the packaged template."""
    try:
        result = init_workspace(target, force=force)
    except (FileExistsError, FileNotFoundError, NotADirectoryError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"AITest workspace initialized: {result.target}")
    click.echo(f"Copied files: {len(result.copied_files)}")
    if result.overwritten_files:
        click.echo(f"Overwritten files: {len(result.overwritten_files)}")
    click.echo("")
    click.echo("Next steps:")
    click.echo(f"1. cd {result.target}")
    click.echo("2. Put public docs and API specs under docs/")
    click.echo("3. Edit aitest_config/config.yaml and aitest_config/project_config.yaml")
    click.echo("4. Build knowledge, write Markdown cases, then run:")
    click.echo("   python3 -m aitest_kit.cli codegen <module> --validate-profile")
