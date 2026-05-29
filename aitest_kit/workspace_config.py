"""Workspace-level configuration loading for AITest CLI commands."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


AITEST_CONFIG_PATH = Path("aitest_config/aitest.yaml")
LEGACY_CONFIG_PATH = Path("aitest_config/config.yaml")
LEGACY_PROJECT_CONFIG_PATH = Path("aitest_config/project_config.yaml")


@dataclass(frozen=True)
class WorkspacePaths:
    cases_dir: Path
    generated_dir: Path
    profile_dir: Path
    reports_dir: Path
    project_config: Path


def load_workspace_paths() -> WorkspacePaths:
    """Load path settings from aitest.yaml or legacy config.yaml."""
    raw = _workspace_paths_data()
    return WorkspacePaths(
        cases_dir=Path(raw.get("cases_dir", "test_workspace/cases")),
        generated_dir=Path(
            raw.get("generated_dir")
            or raw.get("generated_root")
            or "test_workspace/tests/generated"
        ),
        profile_dir=Path(
            raw.get("profile_dir")
            or raw.get("fixtures_dir")
            or "test_workspace/tests/fixtures"
        ),
        reports_dir=Path(
            raw.get("reports_dir")
            or raw.get("reports_root")
            or "test_workspace/reports"
        ),
        project_config=Path(raw.get("project_config", LEGACY_PROJECT_CONFIG_PATH)),
    )


def load_codegen_config_data(path: str | Path = LEGACY_PROJECT_CONFIG_PATH) -> dict[str, Any] | None:
    """Load the codegen config mapping from aitest.yaml or project_config.yaml.

    ``aitest_config/aitest.yaml`` wins only when it has a non-empty ``codegen``
    section and the caller is using the default project-config path. Explicit
    project-config paths keep their legacy behavior.
    """
    config_path = Path(path)
    if config_path == LEGACY_PROJECT_CONFIG_PATH and AITEST_CONFIG_PATH.exists():
        data = _read_yaml_mapping(AITEST_CONFIG_PATH)
        codegen = data.get("codegen")
        if isinstance(codegen, dict) and codegen:
            return codegen

    if not config_path.exists():
        return None
    return _read_yaml_mapping(config_path)


def has_workspace_config() -> bool:
    """Return whether the workspace has either new or legacy config files."""
    return AITEST_CONFIG_PATH.exists() or (
        LEGACY_CONFIG_PATH.exists() and LEGACY_PROJECT_CONFIG_PATH.exists()
    )


def _workspace_paths_data() -> dict[str, Any]:
    if AITEST_CONFIG_PATH.exists():
        data = _read_yaml_mapping(AITEST_CONFIG_PATH)
        workspace = data.get("workspace", {})
        if isinstance(workspace, dict):
            paths = workspace.get("paths", {})
            if isinstance(paths, dict):
                return dict(paths)
        paths = data.get("paths", {})
        return dict(paths) if isinstance(paths, dict) else {}

    if LEGACY_CONFIG_PATH.exists():
        data = _read_yaml_mapping(LEGACY_CONFIG_PATH)
        paths = data.get("paths", {})
        return dict(paths) if isinstance(paths, dict) else {}

    return {}


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise RuntimeError(f"无法读取 AITest 配置 {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"AITest 配置 {path} 必须是 YAML mapping")
    return data
