"""CLI entry point for aitest-kit."""
from __future__ import annotations

import click

from aitest_kit.codegen.cli import codegen
from aitest_kit.doctor import doctor_command
from aitest_kit.init_workspace import init_command
from aitest_kit.report.cli import report_command, run_command


@click.group()
def main():
    """AI-driven testing toolkit for Markdown cases, codegen, and pytest reports."""


main.add_command(codegen)
main.add_command(doctor_command)
main.add_command(init_command)
main.add_command(run_command)
main.add_command(report_command)


if __name__ == "__main__":
    main()
