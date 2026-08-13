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
from aitest_kit.registry.path_resolver import merge_knowledge_refs, resolve_knowledge_refs
from aitest_kit.registry.models import ModuleBinding


@dataclass(frozen=True)
class SuiteContext:
    suite_dir: Path
    target: str
    module: str
    suite: str
    case_files: list[Path]
    manifest_path: Path | None
    module_profile_path: Path
    suite_profile_path: Path
    runtime_profile: RuntimeProfile
    module_binding: ModuleBinding | None = None
    knowledge_refs: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SuiteRuntimePaths:
    generated_dir: Path
    reports_dir: Path
    profile_dir: Path


def _read_manifest(path: Path) -> tuple[dict[str, Any], list[str]]:
    if not path.exists():
        return {}, []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return {}, [f"E610: suite.yaml is invalid: {exc}"]
    if not isinstance(data, dict):
        return {}, ["E610: suite.yaml root must be a mapping"]
    return data, []


def _display_path(path: Path) -> Path:
    try:
        return path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return path.resolve()


def suite_output_file_type(context: SuiteContext, case_path: Path) -> str:
    """Return the generated output file type suffix for one suite case file."""
    return f"{context.suite}_{Path(case_path).stem}"


def suite_generated_path(generated_dir: str | Path, context: SuiteContext, case_path: Path) -> Path:
    """Return the generated pytest path for one suite case file."""
    return Path(generated_dir) / f"test_{context.module}_{suite_output_file_type(context, case_path)}.py"


def _case_files_from_manifest(
    suite_dir: Path,
    manifest: dict[str, Any],
    diagnostics: list[str],
) -> list[Path]:
    raw_files = manifest.get("case_files")
    if raw_files is None:
        diagnostics.append("E610: suite.yaml requires case_files")
        return []
    if not isinstance(raw_files, list):
        diagnostics.append("E610: suite.yaml case_files must be a list")
        return []

    paths: list[Path] = []
    for item in raw_files:
        if not isinstance(item, str) or not item.strip():
            diagnostics.append("E610: suite.yaml case_files values must be strings")
            continue
        path = suite_dir / item
        if not path.exists():
            diagnostics.append(f"E614: suite case file not found: {path}")
            continue
        paths.append(path)
    return paths


_FORBIDDEN_SUITE_MANIFEST_FIELDS = {
    "profile",
    "fixture",
    "fixtures",
    "helper",
    "helpers",
    "module_type",
    "case_flows",
    "case_bodies",
    "requests",
    "variables",
    "case_fixtures",
    "extra_imports",
    "assertion_rules",
    "structured_assertions",
    "default_fixture",
    "default_object",
    "default_case_setup",
    "case_ids",
    "include_manual",
    "pytest_args",
    "env_file",
    "allow_risk",
}


def _validate_strict_suite_manifest(
    manifest_path: Path,
    manifest: dict[str, Any],
    diagnostics: list[str],
) -> None:
    if not manifest_path.exists():
        return
    for key in ("target", "module", "suite"):
        value = manifest.get(key)
        if not isinstance(value, str) or not value.strip():
            diagnostics.append(f"E610: suite.yaml requires {key}")
    forbidden = sorted(_FORBIDDEN_SUITE_MANIFEST_FIELDS & set(manifest))
    if forbidden:
        diagnostics.append(
            "E610: suite.yaml must not contain generation or execution fields: "
            + ", ".join(forbidden)
        )


def load_suite_context(
    cases_path: str | Path,
    *,
    profile_dir: str | Path = "test_workspace/targets",
) -> SuiteContext:
    """Load suite manifest, case files, module profile and optional suite profile."""
    suite_input = Path(cases_path)
    if suite_input.is_file():
        suite_dir = suite_input.parent
        manifest_path = suite_input
    else:
        suite_dir = suite_input
        manifest_path = _manifest_path_for_dir(suite_dir)
    diagnostics: list[str] = []
    if not suite_dir.exists() or not suite_dir.is_dir():
        diagnostics.append(f"E610: case suite directory not found: {suite_dir}")

    manifest, manifest_errors = _read_manifest(manifest_path)
    diagnostics.extend(manifest_errors)
    has_manifest = manifest_path.exists() and not manifest_errors
    if not manifest_path.exists():
        diagnostics.append(f"E610: suite.yaml not found: {manifest_path}")
    if has_manifest:
        _validate_strict_suite_manifest(manifest_path, manifest, diagnostics)

    target = manifest.get("target", "") if has_manifest else ""
    if target is None:
        target = ""
    elif not isinstance(target, str):
        diagnostics.append("E610: suite manifest target must be a string")
        target = ""

    module = manifest.get("module")
    if not isinstance(module, str) or not module.strip():
        diagnostics.append("E610: suite.yaml requires module")
        module = ""

    suite = manifest.get("suite") if has_manifest else suite_dir.name
    if not isinstance(suite, str) or not suite.strip():
        diagnostics.append("E610: suite manifest requires suite")
        suite = suite_dir.name

    case_files = _case_files_from_manifest(suite_dir, manifest, diagnostics)
    if not case_files and not diagnostics:
        diagnostics.append(f"E614: no Markdown case files found in {suite_dir}")

    profile_name = _default_suite_profile_name(suite)
    suite_profile_path = suite_dir / profile_name
    if suite_profile_path.exists() and not suite_profile_path.name.endswith("_suite.md"):
        diagnostics.append(
            f"E612: suite profile filename must end with _suite.md: {suite_profile_path.name}"
        )

    module_profile_path = (
        Path(profile_dir) / target / "modules" / module / "profile.md"
    )
    suite_data = load_profile_yaml(suite_profile_path) if suite_profile_path.exists() else {}
    if suite_profile_path.exists():
        _validate_suite_identity(suite_data, module, suite, diagnostics)
    merged, merge_diagnostics = merge_profile_yaml({}, suite_data)
    diagnostics.extend(merge_diagnostics)

    knowledge_refs = resolve_knowledge_refs(
        manifest.get("knowledge_refs", {}),
        base_dir=Path.cwd().resolve(),
        diagnostics=diagnostics,
        field="knowledge_refs",
    )

    runtime_profile = RuntimeProfile(
        data=merged,
        module_profile_path=module_profile_path,
        suite_profile_path=suite_profile_path if suite_profile_path.exists() else None,
        diagnostics=list(diagnostics),
    )

    return SuiteContext(
        suite_dir=suite_dir,
        target=target.strip(),
        module=module,
        suite=suite,
        case_files=[_display_path(path) for path in case_files],
        manifest_path=manifest_path if manifest_path.exists() else None,
        module_profile_path=module_profile_path,
        suite_profile_path=suite_profile_path,
        runtime_profile=runtime_profile,
        knowledge_refs=knowledge_refs,
        diagnostics=diagnostics,
    )


def load_suite_context_for_paths(
    cases_path: str | Path,
    *,
    profile_dir: str | Path = "test_workspace/targets",
) -> SuiteContext:
    """Load a suite, preferring target profile defaults when target config exists."""
    context = load_suite_context(
        cases_path,
        profile_dir=profile_dir,
    )
    target_context = _load_target_context_if_available(context.target)
    if target_context is None:
        diagnostics = list(context.diagnostics)
        if context.target:
            diagnostics.append(
                f"E616: target registry not found for suite target: {context.target}"
            )
        runtime_profile = RuntimeProfile(
            data=dict(context.runtime_profile.data),
            module_profile_path=context.module_profile_path,
            suite_profile_path=context.runtime_profile.suite_profile_path,
            diagnostics=diagnostics,
        )
        return _replace_suite_context(
            context,
            runtime_profile=runtime_profile,
            knowledge_refs=context.knowledge_refs,
            module_binding=None,
            diagnostics=diagnostics,
        )
    return _with_target_module_binding(context, target_context)


def resolve_suite_runtime_paths(
    context: SuiteContext,
    *,
    generated_dir: str | Path,
    reports_dir: str | Path,
    profile_dir: str | Path,
) -> SuiteRuntimePaths:
    """Resolve generated/report/profile directories for a suite.

    If a suite target has a registry config, target defaults win. Otherwise the
    caller-provided workspace directories are preserved.
    """
    target_context = _load_target_context_if_available(context.target)
    if target_context is None:
        return SuiteRuntimePaths(
            generated_dir=Path(generated_dir),
            reports_dir=Path(reports_dir),
            profile_dir=Path(profile_dir),
        )
    return SuiteRuntimePaths(
        generated_dir=target_context.defaults.generated_dir,
        reports_dir=target_context.defaults.reports_dir,
        profile_dir=target_context.defaults.module_dir,
    )


def _load_target_context_if_available(target: str):
    if not target:
        return None
    from aitest_kit.registry.loader import load_target_context

    context = load_target_context(target)
    if context.config_path is None:
        return None
    return context


def _with_target_module_binding(context: SuiteContext, target_context) -> SuiteContext:
    """Attach the canonical module package and runtime Harness binding."""
    module_context = _load_module_context_if_available(target_context, context.module)
    knowledge_refs = merge_knowledge_refs(
        target_context.knowledge_refs,
        module_context.knowledge_refs if module_context is not None else {},
        context.knowledge_refs,
    )
    if module_context is None:
        diagnostics = list(context.diagnostics)
        diagnostics.extend(target_context.diagnostics)
        diagnostics.append(
            "E616: canonical module registry not found: "
            f"{target_context.defaults.module_dir / context.module / 'module.yaml'}"
        )
        runtime_profile = RuntimeProfile(
            data={},
            module_profile_path=target_context.defaults.module_dir / context.module / "profile.md",
            suite_profile_path=context.runtime_profile.suite_profile_path,
            module_binding=None,
            diagnostics=diagnostics,
        )
        return _replace_suite_context(
            context,
            runtime_profile=runtime_profile,
            module_profile_path=target_context.defaults.module_dir / context.module / "profile.md",
            knowledge_refs=knowledge_refs,
            module_binding=None,
            diagnostics=diagnostics,
        )

    diagnostics = list(context.diagnostics)
    diagnostics.extend(module_context.diagnostics)
    module_profile_path = module_context.profile_path
    suite_profile_path = context.suite_profile_path
    if not module_profile_path.exists():
        diagnostics.append(f"E611: module profile not found: {module_profile_path}")
    module_data = load_profile_yaml(module_profile_path)
    suite_data = load_profile_yaml(suite_profile_path) if suite_profile_path.exists() else {}
    data, merge_diagnostics = merge_profile_yaml(module_data, suite_data)
    diagnostics.extend(merge_diagnostics)
    if module_context.module_type:
        data["module_type"] = module_context.module_type

    runtime_profile = RuntimeProfile(
        data=data,
        module_profile_path=module_profile_path,
        suite_profile_path=suite_profile_path if suite_profile_path.exists() else None,
        module_binding=module_context.binding,
        diagnostics=diagnostics,
    )
    return _replace_suite_context(
        context,
        runtime_profile=runtime_profile,
        module_profile_path=module_profile_path,
        knowledge_refs=knowledge_refs,
        module_binding=module_context.binding,
        diagnostics=diagnostics,
    )


def _replace_suite_context(
    context: SuiteContext,
    *,
    runtime_profile: RuntimeProfile,
    module_profile_path: Path | None = None,
    knowledge_refs: dict[str, list[Path]],
    module_binding: ModuleBinding | None,
    diagnostics: list[str],
) -> SuiteContext:
    return SuiteContext(
        suite_dir=context.suite_dir,
        target=context.target,
        module=context.module,
        suite=context.suite,
        case_files=context.case_files,
        manifest_path=context.manifest_path,
        module_profile_path=module_profile_path or context.module_profile_path,
        suite_profile_path=context.suite_profile_path,
        runtime_profile=runtime_profile,
        module_binding=module_binding,
        knowledge_refs=knowledge_refs,
        diagnostics=diagnostics,
    )


def _load_module_context_if_available(target_context, module: str):
    module_path = target_context.defaults.module_dir / module / "module.yaml"
    if not module_path.exists():
        return None
    from aitest_kit.registry.loader import load_module_context

    return load_module_context(target_context, module)


def _manifest_path_for_dir(suite_dir: Path) -> Path:
    return suite_dir / "suite.yaml"


def _default_suite_profile_name(suite: str) -> str:
    return f"profile_{suite}_suite.md"


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
