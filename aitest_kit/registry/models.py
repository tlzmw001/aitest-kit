"""Data models for AITest target/module/suite/task registries."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TargetDefaults:
    module_dir: Path
    fixture_dir: Path
    helper_dir: Path
    profile_dir: Path
    suite_dir: Path
    generated_dir: Path
    reports_dir: Path


@dataclass(frozen=True)
class TargetContext:
    workspace_root: Path
    target: str
    config_path: Path | None
    source_root: Path | None
    docs: list[Path]
    defaults: TargetDefaults
    knowledge_refs: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RegisteredSuite:
    suite: str
    manifest: Path
    status: str = "active"


@dataclass(frozen=True)
class ModuleContext:
    workspace_root: Path
    target: str
    module: str
    module_type: str
    config_path: Path | None
    knowledge_refs: dict[str, Any]
    fixture_path: Path | None
    default_fixture: str
    profile_path: Path | None
    helper_paths: list[Path]
    registered_suites: list[RegisteredSuite]
    diagnostics: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SuiteManifestContext:
    workspace_root: Path
    target: str
    module: str
    suite: str
    manifest_path: Path
    case_files: list[Path]
    profile_path: Path
    knowledge_refs: dict[str, Any]
    diagnostics: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TaskDefaults:
    include_manual: bool | None = None
    pytest_args: list[str] = field(default_factory=list)
    allow_risk: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TaskUnit:
    target: str
    name: str = ""
    module: str = ""
    suite: str = ""
    suite_file: Path | None = None
    case_ids: list[str] = field(default_factory=list)
    include_manual: bool | None = None
    pytest_args: list[str] = field(default_factory=list)
    allow_risk: list[str] = field(default_factory=list)
    all: bool = False


@dataclass(frozen=True)
class TaskContext:
    workspace_root: Path
    task: str
    task_path: Path
    units: list[TaskUnit]
    description: str = ""
    env_files: list[Path] = field(default_factory=list)
    defaults: TaskDefaults = field(default_factory=TaskDefaults)
    diagnostics: list[str] = field(default_factory=list)
