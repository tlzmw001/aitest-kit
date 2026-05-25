"""Case-suite loading and runtime profile assembly for codegen."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from aitest_kit.codegen.parser import ParseResult, parse_case_file
from aitest_kit.codegen.profile import (
    RuntimeProfile,
    load_profile_yaml,
    merge_profile_yaml,
)


@dataclass(frozen=True)
class SuiteContext:
    suite_dir: Path
    module: str
    suite: str
    case_files: list[Path]
    manifest_path: Path | None
    module_profile_path: Path
    suite_profile_path: Path
    runtime_profile: RuntimeProfile
    knowledge_refs: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[str] = field(default_factory=list)


def _read_manifest(path: Path) -> tuple[dict[str, Any], list[str]]:
    if not path.exists():
        return {}, []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return {}, [f"E610: aitest_suite.yaml is invalid: {exc}"]
    if not isinstance(data, dict):
        return {}, ["E610: aitest_suite.yaml root must be a mapping"]
    return data, []


def _display_path(path: Path) -> Path:
    try:
        return path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return path.resolve()


def _scan_case_files(suite_dir: Path) -> list[Path]:
    result: list[Path] = []
    for path in sorted(suite_dir.glob("*.md")):
        if path.name == "README.md" or path.name.startswith("codegen_profile_"):
            continue
        parsed = parse_case_file(path)
        if parsed.cases:
            result.append(path)
    return result


def _case_files_from_manifest(
    suite_dir: Path,
    manifest: dict[str, Any],
    diagnostics: list[str],
) -> list[Path]:
    raw_files = manifest.get("case_files")
    if raw_files is None:
        return _scan_case_files(suite_dir)
    if not isinstance(raw_files, list):
        diagnostics.append("E610: aitest_suite.yaml case_files must be a list")
        return []

    paths: list[Path] = []
    for item in raw_files:
        if not isinstance(item, str) or not item.strip():
            diagnostics.append("E610: aitest_suite.yaml case_files values must be strings")
            continue
        path = suite_dir / item
        if not path.exists():
            diagnostics.append(f"E614: suite case file not found: {path}")
            continue
        paths.append(path)
    return paths


def load_suite_context(
    cases_path: str | Path,
    *,
    module_override: str | None = None,
    profile_dir: str | Path = "test_workspace/tests/fixtures",
) -> SuiteContext:
    """Load suite manifest, case files, module profile and optional suite profile."""
    suite_dir = Path(cases_path)
    diagnostics: list[str] = []
    if not suite_dir.exists() or not suite_dir.is_dir():
        diagnostics.append(f"E610: case suite directory not found: {suite_dir}")

    manifest_path = suite_dir / "aitest_suite.yaml"
    manifest, manifest_errors = _read_manifest(manifest_path)
    diagnostics.extend(manifest_errors)
    has_manifest = manifest_path.exists() and not manifest_errors

    module = module_override or manifest.get("module")
    if not isinstance(module, str) or not module.strip():
        diagnostics.append("E610: suite manifest requires module, or pass --module")
        module = module_override or ""

    if module_override and isinstance(manifest.get("module"), str) and manifest["module"] != module_override:
        diagnostics.append(
            f"E610: --module {module_override} conflicts with manifest module {manifest['module']}"
        )

    suite = manifest.get("suite") if has_manifest else suite_dir.name
    if not isinstance(suite, str) or not suite.strip():
        diagnostics.append("E610: suite manifest requires suite")
        suite = suite_dir.name

    case_files = _case_files_from_manifest(suite_dir, manifest, diagnostics)
    if not case_files and not diagnostics:
        diagnostics.append(f"E614: no Markdown case files found in {suite_dir}")

    profile_name = manifest.get("profile") or f"codegen_profile_{suite}_suite.md"
    if not isinstance(profile_name, str) or not profile_name.strip():
        diagnostics.append("E610: suite manifest profile must be a string")
        profile_name = f"codegen_profile_{suite}_suite.md"
    suite_profile_path = suite_dir / profile_name
    if suite_profile_path.exists() and not suite_profile_path.name.endswith("_suite.md"):
        diagnostics.append(
            f"E612: suite profile filename must end with _suite.md: {suite_profile_path.name}"
        )

    module_profile_path = Path(profile_dir) / f"codegen_profile_{module}.md"
    if module and not module_profile_path.exists():
        diagnostics.append(f"E611: module profile not found: {module_profile_path}")

    module_data = load_profile_yaml(module_profile_path)
    suite_data = load_profile_yaml(suite_profile_path) if suite_profile_path.exists() else {}
    if suite_profile_path.exists():
        _validate_suite_identity(suite_data, module, suite, diagnostics)
    merged, merge_diagnostics = merge_profile_yaml(module_data, suite_data)
    diagnostics.extend(merge_diagnostics)

    knowledge_refs = manifest.get("knowledge_refs", {})
    if not isinstance(knowledge_refs, dict):
        diagnostics.append("E610: suite manifest knowledge_refs must be a mapping")
        knowledge_refs = {}

    runtime_profile = RuntimeProfile(
        data=merged,
        module_profile_path=module_profile_path,
        suite_profile_path=suite_profile_path if suite_profile_path.exists() else None,
        diagnostics=list(diagnostics),
    )

    return SuiteContext(
        suite_dir=suite_dir,
        module=module,
        suite=suite,
        case_files=[_display_path(path) for path in case_files],
        manifest_path=manifest_path if manifest_path.exists() else None,
        module_profile_path=module_profile_path,
        suite_profile_path=suite_profile_path,
        runtime_profile=runtime_profile,
        knowledge_refs=dict(knowledge_refs),
        diagnostics=diagnostics,
    )


def _validate_suite_identity(
    suite_data: dict[str, Any],
    module: str,
    suite: str,
    diagnostics: list[str],
) -> None:
    if suite_data.get("profile_scope") != "case_suite":
        diagnostics.append("E613: suite profile profile_scope must be case_suite")
    parent_module = suite_data.get("parent_module")
    if parent_module is not None and parent_module != module:
        diagnostics.append(
            f"E613: suite profile parent_module {parent_module} does not match {module}"
        )
    profile_suite = suite_data.get("suite")
    if profile_suite is not None and profile_suite != suite:
        diagnostics.append(
            f"E613: suite profile suite {profile_suite} does not match {suite}"
        )


def parse_suite_case_file(path: Path, module: str) -> ParseResult:
    """Parse a suite case file and force the owning L1 module."""
    parse_result = parse_case_file(path)
    parse_result.module = module
    return parse_result
