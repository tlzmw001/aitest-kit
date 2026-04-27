"""codegen CLI — parse Markdown cases and invoke test-codegen skill."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click
import yaml

from aitest_kit.codegen.parser import parse_case_file


def _load_cases_dir() -> Path:
    config_path = Path("aitest_config/config.yaml")
    if config_path.exists():
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        return Path(cfg.get("paths", {}).get("cases_dir", "test_workspace/cases"))
    return Path("test_workspace/cases")


def _list_modules(cases_dir: Path) -> list[str]:
    return sorted(d.name for d in cases_dir.iterdir() if d.is_dir() and not d.name.startswith("."))


@click.command()
@click.argument("module", required=False)
@click.option("--all", "all_modules", is_flag=True, help="Generate for all modules")
@click.option("--dry-run", is_flag=True, help="Parse only, show what would be generated")
def codegen(module: str | None, all_modules: bool, dry_run: bool):
    """Generate pytest from Markdown test cases."""
    cases_dir = _load_cases_dir()

    if all_modules:
        modules = _list_modules(cases_dir)
    elif module:
        modules = [module]
    else:
        click.echo("Usage: aitest codegen <module> or aitest codegen --all")
        sys.exit(1)

    for mod in modules:
        mod_dir = cases_dir / mod
        if not mod_dir.exists():
            click.echo(f"[SKIP] {mod}: directory not found at {mod_dir}")
            continue

        click.echo(f"\n{'='*60}")
        click.echo(f"Module: {mod}")
        click.echo(f"{'='*60}")

        for md_file in ["business.md", "boundary.md"]:
            path = mod_dir / md_file
            if not path.exists():
                continue

            result = parse_case_file(path)
            skipped = [tc for tc in result.cases if any("可行性存疑" in m for m in tc.markers)]
            manual = [tc for tc in result.cases if any("manual" in m.lower() for m in tc.markers)]
            auto = [tc for tc in result.cases if tc not in skipped and tc not in manual]

            click.echo(f"\n  {md_file}: {len(result.cases)} cases")
            click.echo(f"    Auto:    {len(auto)}")
            click.echo(f"    Manual:  {len(manual)}")
            click.echo(f"    Skipped: {len(skipped)}")

            if skipped:
                for tc in skipped:
                    click.echo(f"      SKIP {tc.id}: {tc.markers}")

            if dry_run:
                click.echo(f"    [dry-run] would generate test_workspace/tests/generated/test_{mod}_{md_file.replace('.md','')}.py")
                continue

            click.echo(f"    → Run /test-codegen {mod} to generate pytest files via skill")

    if dry_run:
        click.echo("\n[dry-run] No files generated.")
