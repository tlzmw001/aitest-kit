"""codegen CLI — parse and emit pytest from Markdown test cases."""
from __future__ import annotations

import ast
import sys
import tempfile
import difflib
from pathlib import Path

import click
import yaml

from aitest_kit.codegen.parser import parse_case_file
from aitest_kit.codegen.emitter import emit_module


def _load_cases_dir() -> Path:
    config_path = Path("aitest_config/config.yaml")
    if config_path.exists():
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        return Path(cfg.get("paths", {}).get("cases_dir", "test_workspace/cases"))
    return Path("test_workspace/cases")


def _list_modules(cases_dir: Path) -> list[str]:
    return sorted(d.name for d in cases_dir.iterdir() if d.is_dir() and not d.name.startswith("."))


def _ast_error(path: Path) -> str | None:
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return f"{path}: {exc.msg} at line {exc.lineno}, column {exc.offset}"
    return None


def _check_consistency(modules: list[str], cases_dir: Path) -> int:
    generated_dir = Path("test_workspace/tests/generated")
    stale_count = 0
    blocked_count = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        for mod in modules:
            mod_dir = cases_dir / mod
            if not mod_dir.exists():
                continue
            results = emit_module(mod, output_dir=tmpdir)
            for r in results:
                if r.diagnostics:
                    click.echo(f"[BLOCKED] {Path(r.output_path).name}")
                    for diag in r.diagnostics:
                        click.echo(f"  {diag}")
                    blocked_count += 1
                    stale_count += 1

        tmp_path = Path(tmpdir)
        all_files = set()
        for f in tmp_path.glob("test_*.py"):
            all_files.add(f.name)
            syntax_error = _ast_error(f)
            if syntax_error:
                click.echo(f"[SYNTAX] {f.name}")
                click.echo(f"  {syntax_error}")
                stale_count += 1
        for f in generated_dir.glob("test_*.py"):
            all_files.add(f.name)

        for fname in sorted(all_files):
            new_file = tmp_path / fname
            old_file = generated_dir / fname

            if not old_file.exists():
                click.echo(f"[NEW] {fname} — not yet in generated/")
                stale_count += 1
                continue
            if not new_file.exists():
                click.echo(f"[EXTRA] {fname} — in generated/ but no source")
                stale_count += 1
                continue

            old_lines = old_file.read_text(encoding="utf-8").splitlines(keepends=True)
            new_lines = new_file.read_text(encoding="utf-8").splitlines(keepends=True)
            diff = list(difflib.unified_diff(
                old_lines, new_lines,
                fromfile=f"generated/{fname}",
                tofile=f"(regenerated) {fname}",
            ))
            if diff:
                click.echo(f"[STALE] {fname}")
                click.echo("".join(diff[:40]))
                stale_count += 1

    if stale_count:
        if blocked_count:
            click.echo(f"\n{blocked_count} file(s) blocked by diagnostics.")
        click.echo(f"\n{stale_count} file(s) stale. Run `aitest codegen --all` to update.")
        return 1

    click.echo("All generated files are up to date.")
    return 0


@click.command()
@click.argument("module", required=False)
@click.option("--all", "all_modules", is_flag=True, help="Generate for all modules")
@click.option("--dry-run", is_flag=True, help="Parse only, show what would be generated")
@click.option("--check", is_flag=True, help="Verify generated files are up to date")
def codegen(module: str | None, all_modules: bool, dry_run: bool, check: bool):
    """Generate pytest from Markdown test cases."""
    if check and dry_run:
        click.echo("Error: --check and --dry-run are mutually exclusive")
        sys.exit(2)

    cases_dir = _load_cases_dir()

    if all_modules:
        modules = _list_modules(cases_dir)
    elif module:
        modules = [module]
    else:
        click.echo("Usage: aitest codegen <module> or aitest codegen --all")
        sys.exit(1)

    if check:
        sys.exit(_check_consistency(modules, cases_dir))

    total_generated = 0
    total_blocked = 0
    total_syntax_errors = 0

    for mod in modules:
        mod_dir = cases_dir / mod
        if not mod_dir.exists():
            click.echo(f"[SKIP] {mod}: directory not found at {mod_dir}")
            continue

        click.echo(f"\n{'='*60}")
        click.echo(f"Module: {mod}")
        click.echo(f"{'='*60}")

        if dry_run:
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
                if result.errors:
                    click.echo("    Errors:")
                    for err in result.errors:
                        click.echo(f"      {err}")
                if skipped:
                    for tc in skipped:
                        click.echo(f"      SKIP {tc.id}: {tc.markers}")
            continue

        results = emit_module(mod)
        blocked = 0
        generated = 0
        syntax_errors = 0
        for r in results:
            click.echo(f"\n  {r.output_path}")
            if r.diagnostics:
                blocked += 1
                click.echo("    Status:   BLOCKED")
                click.echo(f"    Diagnostics: {len(r.diagnostics)}")
                for diag in r.diagnostics:
                    click.echo(f"      {diag}")
                continue

            generated += 1
            click.echo(f"    Cases:    {r.case_count}")
            click.echo(f"    Manual:   {r.manual_count}")
            click.echo(f"    Skipped:  {len(r.skipped)}")
            click.echo(f"    Unparsed: {len(r.unparsed)}")
            if r.unparsed:
                for tc_id, text in r.unparsed:
                    click.echo(f"      {tc_id}: {text[:80]}")
            syntax_error = _ast_error(Path(r.output_path))
            if syntax_error:
                syntax_errors += 1
                click.echo("    Syntax:   ERROR")
                click.echo(f"      {syntax_error}")
            else:
                click.echo("    Syntax:   OK")

        total_generated += generated
        total_blocked += blocked
        total_syntax_errors += syntax_errors
        click.echo(f"\n  Summary: generated={generated}, blocked={blocked}")

    if dry_run:
        click.echo("\n[dry-run] No files generated.")
    else:
        click.echo(
            f"\nFinal summary: generated={total_generated}, "
            f"blocked={total_blocked}, syntax_errors={total_syntax_errors}"
        )
        if total_blocked or total_syntax_errors:
            sys.exit(1)
