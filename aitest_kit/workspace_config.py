"""Workspace-level configuration loading for AITest CLI commands."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


AITEST_CONFIG_PATH = Path("aitest_config/aitest.yaml")


@dataclass(frozen=True)
class WorkspacePaths:
    generated_dir: Path
    profile_dir: Path
    reports_dir: Path
    project_config: Path


def load_workspace_paths() -> WorkspacePaths:
    """Load path settings from aitest.yaml."""
    raw = _workspace_paths_data()
    return WorkspacePaths(
        generated_dir=Path(raw.get("generated_dir", "test_workspace/generated")),
        profile_dir=Path(raw.get("profile_dir", "test_workspace/targets")),
        reports_dir=Path(raw.get("reports_dir", "test_workspace/reports")),
        project_config=AITEST_CONFIG_PATH,
    )


def load_codegen_config_data(path: str | Path = AITEST_CONFIG_PATH) -> dict[str, Any] | None:
    """Load the codegen config mapping from aitest.yaml."""
    if not AITEST_CONFIG_PATH.exists():
        return None
    data = _read_yaml_mapping(AITEST_CONFIG_PATH)
    codegen = data.get("codegen")
    if isinstance(codegen, dict) and codegen:
        return codegen
    return None


def has_workspace_config() -> bool:
    """Return whether the workspace has aitest.yaml."""
    return AITEST_CONFIG_PATH.exists()


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

    return {}


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise RuntimeError(f"无法读取 AITest 配置 {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"AITest 配置 {path} 必须是 YAML mapping")
    return data
