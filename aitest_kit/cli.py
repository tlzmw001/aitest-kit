"""CLI entry point for aitest-kit."""
from __future__ import annotations

import click

from aitest_kit.codegen.cli import codegen


@click.group()
def main():
    """AI-driven automated testing toolkit."""


main.add_command(codegen)


if __name__ == "__main__":
    main()
