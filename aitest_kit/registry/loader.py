"""Load target/module/suite/task registry contexts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from aitest_kit.workspace_config import AITEST_CONFIG_PATH
from aitest_kit.registry.models import (
    ModuleContext,
    RegisteredSuite,
    SuiteManifestContext,
    TargetContext,
    TargetDefaults,
)
from aitest_kit.registry.path_resolver import (
    resolve_named_path,
    resolve_path,
    resolve_path_tree,
)


def load_target_context(
    target: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> TargetContext:
    """Load one target config from target.yaml or aitest_config/targets.yaml."""
    root = Path(workspace_root).expanduser().resolve()
    diagnostics: list[str] = []
    config_path, data = _load_target_data(target, root, diagnostics)

    target_name = _target_name(target, data)
    defaults = _target_defaults(target_name, data.get("defaults", {}), root, diagnostics)
    docs = _resolve_path_list(data.get("docs", []), base_dir=root, diagnostics=diagnostics, field="docs")
    source_root = resolve_path(data.get("source_root"), base_dir=root, diagnostics=diagnostics, field="source_root")
    knowledge_refs = _resolve_mapping(data.get("knowledge_refs", {}), root, diagnostics, "knowledge_refs")

    return TargetContext(
        workspace_root=root,
        target=target_name,
        config_path=config_path,
        source_root=source_root,
        docs=docs,
        defaults=defaults,
        knowledge_refs=knowledge_refs,
        diagnostics=diagnostics,
    )


def load_module_context(
    target_context: TargetContext,
    module: str | Path,
) -> ModuleContext:
    """Load a module registry entry under a target."""
    diagnostics = list(target_context.diagnostics)
    config_path, data = _load_module_data(target_context, module, diagnostics)
    module_name = _module_name(module, data)
    module_type = _module_type(data, diagnostics)

    declared_target = data.get("target")
    if declared_target and declared_target != target_context.target:
        diagnostics.append(
            f"E710: module target {declared_target} does not match target {target_context.target}"
        )

    knowledge_refs = _resolve_mapping(
        data.get("knowledge_refs", {}),
        target_context.workspace_root,
        diagnostics,
        "knowledge_refs",
    )
    fixture_path, default_fixture = _module_fixture(target_context, data, diagnostics)
    profile_path = _module_profile(target_context, data, module_name, diagnostics)
    helper_paths = _module_helpers(target_context, data, diagnostics)
    registered_suites = _registered_suites(target_context, data, diagnostics)

    return ModuleContext(
        workspace_root=target_context.workspace_root,
        target=target_context.target,
        module=module_name,
        module_type=module_type,
        config_path=config_path,
        knowledge_refs=knowledge_refs,
        fixture_path=fixture_path,
        default_fixture=default_fixture,
        profile_path=profile_path,
        helper_paths=helper_paths,
        registered_suites=registered_suites,
        diagnostics=diagnostics,
    )


def load_suite_context(
    suite_file: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> SuiteManifestContext:
    """Load one suite manifest. Directories resolve to suite.yaml."""
    root = Path(workspace_root).expanduser().resolve()
    diagnostics: list[str] = []
    manifest_path = _suite_manifest_path(suite_file, diagnostics)
    data = _read_yaml_mapping(manifest_path, diagnostics, "suite")
    _validate_suite_manifest_shape(data, diagnostics)

    target = _required_string(data, "target", diagnostics)
    module = _required_string(data, "module", diagnostics)
    suite = _required_string(data, "suite", diagnostics) or manifest_path.parent.name

    case_files = _suite_case_files(data, manifest_path, diagnostics)
    profile_path = _suite_profile_path(data, manifest_path, suite, diagnostics)
    knowledge_refs = _resolve_mapping(data.get("knowledge_refs", {}), root, diagnostics, "knowledge_refs")

    return SuiteManifestContext(
        workspace_root=root,
        target=target,
        module=module,
        suite=suite,
        manifest_path=manifest_path,
        case_files=case_files,
        profile_path=profile_path,
        knowledge_refs=knowledge_refs,
        diagnostics=diagnostics,
    )


def _read_yaml_mapping(path: Path, diagnostics: list[str], label: str) -> dict[str, Any]:
    if not path.exists():
        diagnostics.append(f"E700: {label} config not found: {path}")
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        diagnostics.append(f"E700: {label} config is invalid YAML: {exc}")
        return {}
    if not isinstance(data, dict):
        diagnostics.append(f"E700: {label} config root must be a mapping")
        return {}
    return data


def _read_optional_yaml_mapping(path: Path, diagnostics: list[str], label: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return _read_yaml_mapping(path, diagnostics, label)


def _load_target_data(
    target: str | Path,
    root: Path,
    diagnostics: list[str],
) -> tuple[Path | None, dict[str, Any]]:
    raw = Path(target).expanduser()
    is_explicit_path = raw.is_absolute() or len(raw.parts) > 1 or raw.suffix in {".yaml", ".yml"}
    if is_explicit_path:
        path = raw if raw.is_absolute() else root / raw
        path = path.resolve(strict=False)
        return path, _read_yaml_mapping(path, diagnostics, "target")

    target_name = str(target)
    target_file = root / "test_workspace" / "targets" / target_name / "target.yaml"
    if target_file.exists():
        return target_file, _read_yaml_mapping(target_file, diagnostics, "target")

    for targets_file in (root / AITEST_CONFIG_PATH, root / "aitest_config" / "targets.yaml"):
        targets_data = _read_optional_yaml_mapping(targets_file, diagnostics, "targets")
        if targets_data is None:
            continue
        target_data = targets_data.get("targets", {}).get(target_name) if isinstance(targets_data.get("targets"), dict) else None
        if isinstance(target_data, dict):
            return targets_file, target_data
    diagnostics.append(f"E700: target not found: {target_name}")
    return None, {}


def _target_name(target: str | Path, data: dict[str, Any]) -> str:
    if isinstance(data.get("target"), str) and data["target"].strip():
        return data["target"].strip()
    return Path(target).stem if Path(str(target)).suffix else str(target)


def _target_defaults(
    target: str,
    raw: Any,
    root: Path,
    diagnostics: list[str],
) -> TargetDefaults:
    defaults = raw if isinstance(raw, dict) else {}

    def field(name: str, fallback: str) -> Path:
        return resolve_path(
            defaults.get(name, fallback),
            base_dir=root,
            diagnostics=diagnostics,
            field=f"defaults.{name}",
        ) or root / fallback

    return TargetDefaults(
        module_dir=field("module_dir", f"test_workspace/targets/{target}/modules"),
        fixture_dir=field("fixture_dir", f"test_workspace/targets/{target}/fixtures"),
        helper_dir=field("helper_dir", f"test_workspace/targets/{target}/helpers"),
        profile_dir=field("profile_dir", f"test_workspace/targets/{target}/profiles"),
        suite_dir=field("suite_dir", f"test_workspace/suites/{target}"),
        generated_dir=field("generated_dir", f"test_workspace/generated/{target}"),
        reports_dir=field("reports_dir", f"test_workspace/reports/{target}"),
    )


def _load_module_data(
    target_context: TargetContext,
    module: str | Path,
    diagnostics: list[str],
) -> tuple[Path | None, dict[str, Any]]:
    raw = Path(module).expanduser()
    if raw.suffix in {".yaml", ".yml"} or raw.exists():
        path = raw if raw.is_absolute() else target_context.workspace_root / raw
        path = path.resolve(strict=False)
    else:
        path = target_context.defaults.module_dir / f"{module}.yaml"
    data = _read_yaml_mapping(path, diagnostics, "module")
    return path, data


def _module_name(module: str | Path, data: dict[str, Any]) -> str:
    if isinstance(data.get("module"), str) and data["module"].strip():
        return data["module"].strip()
    return Path(module).stem


def _module_type(data: dict[str, Any], diagnostics: list[str]) -> str:
    value = data.get("module_type", "")
    if value in (None, ""):
        return ""
    if not isinstance(value, str):
        diagnostics.append("E711: module_type must be a string")
        return ""
    return value.strip()


def _module_fixture(
    target_context: TargetContext,
    data: dict[str, Any],
    diagnostics: list[str],
) -> tuple[Path | None, str]:
    raw = data.get("fixture", {})
    if isinstance(raw, str):
        file_value = raw
        default_fixture = ""
    elif isinstance(raw, dict):
        file_value = raw.get("file")
        default_fixture = raw.get("default_fixture", "")
    else:
        diagnostics.append("E711: module fixture must be a string or mapping")
        return None, ""
    path = resolve_named_path(
        file_value,
        default_dir=target_context.defaults.fixture_dir,
        workspace_root=target_context.workspace_root,
        diagnostics=diagnostics,
        field="fixture.file",
    )
    return path, default_fixture if isinstance(default_fixture, str) else ""


def _module_profile(
    target_context: TargetContext,
    data: dict[str, Any],
    module: str,
    diagnostics: list[str],
) -> Path | None:
    raw = data.get("profile", {})
    if isinstance(raw, str):
        file_value = raw
    elif isinstance(raw, dict):
        file_value = raw.get("file")
    elif raw:
        diagnostics.append("E711: module profile must be a string or mapping")
        file_value = None
    else:
        file_value = f"profile_{module}.md"
    return resolve_named_path(
        file_value,
        default_dir=target_context.defaults.profile_dir,
        workspace_root=target_context.workspace_root,
        diagnostics=diagnostics,
        field="profile.file",
    )


def _module_helpers(
    target_context: TargetContext,
    data: dict[str, Any],
    diagnostics: list[str],
) -> list[Path]:
    return [
        item
        for item in _resolve_path_list(
            data.get("helpers", []),
            base_dir=target_context.workspace_root,
            diagnostics=diagnostics,
            field="helpers",
        )
        if item is not None
    ]


def _registered_suites(
    target_context: TargetContext,
    data: dict[str, Any],
    diagnostics: list[str],
) -> list[RegisteredSuite]:
    raw = data.get("registered_suites", [])
    if not isinstance(raw, list):
        diagnostics.append("E712: registered_suites must be a list")
        return []
    suites: list[RegisteredSuite] = []
    for index, item in enumerate(raw):
        registered = _registered_suite(target_context, item, index, diagnostics)
        if registered is not None:
            suites.append(registered)
    return suites


def _registered_suite(
    target_context: TargetContext,
    item: Any,
    index: int,
    diagnostics: list[str],
) -> RegisteredSuite | None:
    if isinstance(item, str):
        manifest = resolve_path(
            item,
            base_dir=target_context.workspace_root,
            diagnostics=diagnostics,
            field=f"registered_suites[{index}]",
        )
        if manifest is None:
            return None
        suite = _suite_name_from_manifest(target_context, manifest, index, diagnostics)
        if not suite:
            return None
        return RegisteredSuite(suite=suite, manifest=manifest, status="active")

    if not isinstance(item, dict):
        diagnostics.append(
            f"E712: registered_suites[{index}] must be a suite.yaml path string or a mapping"
        )
        return None

    manifest = resolve_path(
        item.get("manifest"),
        base_dir=target_context.workspace_root,
        diagnostics=diagnostics,
        field=f"registered_suites[{index}].manifest",
    )
    if manifest is None:
        diagnostics.append(f"E712: registered_suites[{index}] requires manifest")
        return None

    suite = item.get("suite")
    if isinstance(suite, str) and suite.strip():
        suite_name = suite.strip()
        if manifest.exists():
            manifest_suite = _suite_name_from_manifest(target_context, manifest, index, diagnostics)
        else:
            manifest_suite = ""
        if manifest_suite and manifest_suite != suite_name:
            diagnostics.append(
                f"E712: registered_suites[{index}].suite {suite_name} "
                f"does not match manifest suite {manifest_suite}"
            )
            return None
    else:
        manifest_suite = _suite_name_from_manifest(target_context, manifest, index, diagnostics)
        if not manifest_suite:
            diagnostics.append(f"E712: registered_suites[{index}] requires suite or readable manifest")
            return None
        suite_name = manifest_suite

    status = item.get("status", "active")
    return RegisteredSuite(suite=suite_name, manifest=manifest, status=str(status))


def _suite_name_from_manifest(
    target_context: TargetContext,
    manifest: Path,
    index: int,
    diagnostics: list[str],
) -> str:
    if not manifest.exists():
        diagnostics.append(f"E712: registered_suites[{index}] suite manifest not found: {manifest}")
        return ""
    suite = load_suite_context(manifest, workspace_root=target_context.workspace_root)
    if suite.diagnostics:
        diagnostics.append(
            f"E712: registered_suites[{index}] invalid suite manifest: "
            + "; ".join(suite.diagnostics)
        )
        return ""
    return suite.suite


def _suite_manifest_path(suite_file: str | Path, diagnostics: list[str]) -> Path:
    path = Path(suite_file).expanduser()
    if path.is_dir():
        candidate = path / "suite.yaml"
        if candidate.exists():
            return candidate.resolve(strict=False)
        diagnostics.append(f"E730: suite directory has no suite.yaml: {path}")
        return candidate.resolve(strict=False)
    return path.resolve(strict=False)


def _suite_case_files(
    data: dict[str, Any],
    manifest_path: Path,
    diagnostics: list[str],
) -> list[Path]:
    raw = data.get("case_files", [])
    if "case_files" not in data:
        diagnostics.append("E731: suite case_files is required")
        return []
    if not isinstance(raw, list):
        diagnostics.append("E731: suite case_files must be a list")
        return []
    result: list[Path] = []
    for index, item in enumerate(raw):
        path = resolve_path(
            item,
            base_dir=manifest_path.parent,
            diagnostics=diagnostics,
            field=f"case_files[{index}]",
        )
        if path is not None:
            result.append(path)
    return result


def _suite_profile_path(
    data: dict[str, Any],
    manifest_path: Path,
    suite: str,
    diagnostics: list[str],
) -> Path:
    profile = data.get("profile")
    if profile is None:
        profile = f"profile_{suite}_suite.md"
    return resolve_path(
        profile,
        base_dir=manifest_path.parent,
        diagnostics=diagnostics,
        field="profile",
    ) or (manifest_path.parent / f"profile_{suite}_suite.md").resolve(strict=False)


_FORBIDDEN_SUITE_MANIFEST_FIELDS = {
    "fixture",
    "fixtures",
    "helper",
    "helpers",
    "module_type",
    "case_flows",
    "case_bodies",
    "request_overrides",
    "variables",
    "case_fixtures",
    "extra_imports",
    "assertion_rules",
    "default_fixture",
    "default_object",
    "default_case_setup",
    "case_ids",
    "include_manual",
    "pytest_args",
    "env_file",
    "allow_risk",
}


def _validate_suite_manifest_shape(data: dict[str, Any], diagnostics: list[str]) -> None:
    forbidden = sorted(_FORBIDDEN_SUITE_MANIFEST_FIELDS & set(data))
    if forbidden:
        diagnostics.append(
            "E731: suite manifest must not contain generation or execution fields: "
            + ", ".join(forbidden)
        )


def _required_string(data: dict[str, Any], key: str, diagnostics: list[str]) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        diagnostics.append(f"E700: {key} is required")
        return ""
    return value.strip()


def _resolve_mapping(
    value: Any,
    base_dir: Path,
    diagnostics: list[str],
    field: str,
) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        diagnostics.append(f"E700: {field} must be a mapping")
        return {}
    resolved = resolve_path_tree(value, base_dir=base_dir, diagnostics=diagnostics, field=field)
    return resolved if isinstance(resolved, dict) else {}


def _resolve_path_list(
    value: Any,
    *,
    base_dir: Path,
    diagnostics: list[str],
    field: str,
) -> list[Path]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        diagnostics.append(f"E700: {field} must be a list")
        return []
    paths: list[Path] = []
    for index, item in enumerate(value):
        path = resolve_path(item, base_dir=base_dir, diagnostics=diagnostics, field=f"{field}[{index}]")
        if path is not None:
            paths.append(path)
    return paths
