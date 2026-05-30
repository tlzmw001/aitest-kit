"""CLI entry point for aitest-kit."""
from __future__ import annotations

import click

from aitest_kit.codegen.cli import codegen
from aitest_kit.doctor import doctor_command
from aitest_kit.init_workspace import init_command
from aitest_kit.registry.cli import registry_command, task_command
from aitest_kit.report.cli import report_command, run_command
from aitest_kit.upgrade_workspace import upgrade_command


@click.group()
def main():
    """AI-driven testing toolkit for Markdown cases, codegen, and pytest reports.

    \b
    Command map:
      init      create a clean AITest workspace skeleton
      doctor    diagnose workspace, registry, profile, generated pytest
      codegen   compile Markdown suites/tasks into generated pytest
      run       execute generated pytest and write structured reports
      report    re-render report.md from existing result.json
      registry  wire suites into module/target/all aggregation
      task      create explicit multi-suite execution manifests
      upgrade   update template-managed workspace files
    """


main.add_command(codegen)
main.add_command(doctor_command)
main.add_command(init_command)
main.add_command(registry_command)
main.add_command(run_command)
main.add_command(report_command)
main.add_command(task_command)
main.add_command(upgrade_command)


if __name__ == "__main__":
    main()
