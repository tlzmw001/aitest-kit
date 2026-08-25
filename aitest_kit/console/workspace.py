from __future__ import annotations

import json
import logging
import re
import subprocess
import threading
from pathlib import Path
from typing import Any

from aitest_kit.codegen.suite import parse_suite_case_file
from aitest_kit.console.errors import ConsoleError
from aitest_kit.registry import (
    load_module_context,
    load_suite_context,
    load_target_context,
    load_task_context,
)
from aitest_kit.workspace import init_workspace as create_workspace
from aitest_kit.workspace_config import AITEST_CONFIG_PATH, WorkspacePaths, load_workspace_paths


_CASE_HEADER = re.compile(r"^###\s+(TC-[A-Z0-9]+-\d+)[：:]", re.MULTILINE)
_LOGGER = logging.getLogger(__name__)
_REQUIRED_WORKSPACE_PATHS = (Path("aitest_config/aitest.yaml"), Path("test_workspace"))


class WorkspaceState:
    """Single active workspace and explicitly granted external env files."""

    def __init__(self, initial_workspace: str | Path | None = None) -> None:
        self._lock = threading.RLock()
        self._root: Path | None = None
        self._external_env_grants: set[Path] = set()
        self._active_env_file: Path | None = None
        if initial_workspace is not None:
            self.open(initial_workspace)

    @property
    def root(self) -> Path:
        with self._lock:
            if self._root is None:
                raise ConsoleError("WORKSPACE_NOT_OPEN", "尚未打开 AITest workspace", status_code=409)
            return self._root

    def open(self, raw_path: str | Path) -> Path:
        path = Path(raw_path).expanduser().resolve(strict=False)
        if not path.exists() or not path.is_dir():
            raise ConsoleError("WORKSPACE_INVALID", f"Workspace 目录不存在：{path}")
        required = tuple(path / relative for relative in _REQUIRED_WORKSPACE_PATHS)
        missing = [str(item.relative_to(path)) for item in required if not item.exists()]
        if missing:
            if len(missing) == len(required):
                raise ConsoleError(
                    "WORKSPACE_NOT_INITIALIZED",
                    "该目录尚未初始化为 AITest workspace",
                    status_code=409,
                )
            raise ConsoleError(
                "WORKSPACE_INVALID",
                "AITest workspace 结构不完整，缺少：" + "、".join(missing),
            )
        try:
            paths = _workspace_paths(path)
            _target_contexts(path, paths.profile_dir)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ConsoleError("WORKSPACE_INVALID", "AITest workspace 配置无法解析") from exc
        with self._lock:
            self._root = path
            self._external_env_grants.clear()
            self._active_env_file = None
        return path

    @property
    def paths(self) -> WorkspacePaths:
        try:
            return _workspace_paths(self.root)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ConsoleError("WORKSPACE_INVALID", "AITest workspace 配置无法解析") from exc

    def initialize(self, raw_path: str | Path) -> Path:
        """Initialize an existing directory without overwriting template-managed files."""
        path = Path(raw_path).expanduser().resolve(strict=False)
        if not path.exists() or not path.is_dir():
            raise ConsoleError("WORKSPACE_INVALID", f"Workspace 目录不存在：{path}")
        existing_markers = [relative for relative in _REQUIRED_WORKSPACE_PATHS if (path / relative).exists()]
        if len(existing_markers) == len(_REQUIRED_WORKSPACE_PATHS):
            raise ConsoleError("WORKSPACE_ALREADY_INITIALIZED", "该目录已经是 AITest workspace", status_code=409)
        if existing_markers:
            raise ConsoleError(
                "WORKSPACE_INVALID",
                "目录中存在不完整的 AITest workspace 结构，请先人工检查",
                status_code=409,
            )
        try:
            create_workspace(path, force=False)
        except FileExistsError as exc:
            raise ConsoleError(
                "WORKSPACE_INIT_CONFLICT",
                str(exc),
                status_code=409,
            ) from exc
        except OSError as exc:
            _LOGGER.exception("Failed to initialize AITest workspace at %s", path)
            raise ConsoleError(
                "WORKSPACE_INIT_FAILED",
                "初始化 AITest workspace 时写入失败",
                status_code=500,
            ) from exc
        return self.open(path)

    def resolve_inside(self, raw_path: str | Path, *, allow_missing: bool = False) -> Path:
        root = self.root
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = root / path
        path = path.resolve(strict=False)
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ConsoleError(
                "PATH_OUTSIDE_WORKSPACE",
                "路径不在当前 workspace 内",
                status_code=403,
            ) from exc
        if not allow_missing and not path.exists():
            raise ConsoleError("FILE_NOT_FOUND", "文件不存在", status_code=404)
        return path

    def relative(self, path: Path) -> str:
        try:
            return path.resolve(strict=False).relative_to(self.root).as_posix()
        except ValueError:
            return str(path.resolve(strict=False))

    def grant_external_env(self, raw_path: str | Path) -> Path:
        path = Path(raw_path).expanduser().resolve(strict=False)
        if not path.exists() or not path.is_file():
            raise ConsoleError("ENV_PATH_NOT_AUTHORIZED", "只能授权已存在的 env 文件", status_code=403)
        with self._lock:
            self._external_env_grants.add(path)
        return path

    def set_active_env(self, raw_path: str | Path | None) -> Path | None:
        if raw_path in (None, ""):
            with self._lock:
                self._active_env_file = None
            return None
        path = self.resolve_env(raw_path, allow_missing=False)
        with self._lock:
            self._active_env_file = path
        return path

    @property
    def active_env_file(self) -> Path | None:
        with self._lock:
            return self._active_env_file

    def env_paths(self) -> list[Path]:
        root = self.root
        paths: list[Path] = [root / ".env"]
        tasks_dir = root / "test_workspace" / "tasks"
        for task_path in sorted(tasks_dir.glob("*.yaml")) if tasks_dir.exists() else []:
            context = load_task_context(task_path, workspace_root=root)
            paths.extend(item for item in context.env_files if _inside(root, item))
        with self._lock:
            if self._active_env_file is not None:
                paths.append(self._active_env_file)
            paths.extend(sorted(self._external_env_grants))
        unique: list[Path] = []
        seen: set[Path] = set()
        for path in paths:
            resolved = path.expanduser().resolve(strict=False)
            if resolved not in seen:
                unique.append(resolved)
                seen.add(resolved)
        return unique

    def asset_roots(self) -> dict[str, tuple[Path, ...]]:
        root = self.root
        paths = self.paths
        contexts = _target_contexts(root, paths.profile_dir)
        groups: dict[str, list[Path]] = {
            "profiles": [paths.profile_dir],
            "modules": [],
            "helpers": [],
            "suites": [],
            "generated": [paths.generated_dir],
            "reports": [paths.reports_dir],
        }
        for context in contexts:
            groups["modules"].append(context.defaults.module_dir)
            groups["helpers"].append(context.defaults.helper_dir)
            groups["suites"].append(context.defaults.suite_dir)
            groups["generated"].append(context.defaults.generated_dir)
            groups["reports"].append(context.defaults.reports_dir)
        return {name: tuple(_unique_paths(values)) for name, values in groups.items()}

    def resolve_env(self, raw_path: str | Path, *, allow_missing: bool) -> Path:
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = (self.root / path).resolve(strict=False)
        else:
            path = path.resolve(strict=False)
        allowed = set(self.env_paths())
        if path not in allowed:
            raise ConsoleError(
                "ENV_PATH_NOT_AUTHORIZED",
                "该 env 文件尚未获得当前 Console 会话授权",
                status_code=403,
            )
        if not allow_missing and (not path.exists() or not path.is_file()):
            raise ConsoleError("FILE_NOT_FOUND", "Env 文件不存在", status_code=404)
        return path

    def snapshot(self) -> dict[str, Any]:
        root = self.root
        targets = _targets_snapshot(root, self.paths.profile_dir)
        tasks = _tasks_snapshot(root)
        case_count = sum(
            len(suite["cases"])
            for target in targets
            for module in target["modules"]
            for suite in module["suites"]
        )
        return {
            "name": root.name,
            "path": str(root),
            "branch": _git_branch(root),
            "counts": {
                "targets": len(targets),
                "modules": sum(len(target["modules"]) for target in targets),
                "suites": sum(len(module["suites"]) for target in targets for module in target["modules"]),
                "cases": case_count,
                "tasks": len(tasks),
            },
            "targets": targets,
            "tasks": tasks,
            "recent_reports": self.list_reports(limit=5),
        }

    def list_reports(self, *, limit: int = 100) -> list[dict[str, Any]]:
        reports: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for reports_root in self.asset_roots()["reports"]:
            if not reports_root.exists():
                continue
            for path in reports_root.rglob("result.json"):
                if "latest" in path.parts or "units" in path.parts:
                    continue
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError):
                    continue
                run_id = str(data.get("run_id", ""))
                key = (run_id, str(path.parent.resolve(strict=False)))
                if not run_id or key in seen:
                    continue
                seen.add(key)
                reports.append(_report_summary(self, path, data))
        reports.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
        return reports[:limit]

    def report_detail(self, relative_result_path: str) -> dict[str, Any]:
        path = self.resolve_inside(relative_result_path)
        if not any(_inside(root, path) for root in self.asset_roots()["reports"]):
            raise ConsoleError("FILE_READ_ONLY", "报告路径无效", status_code=403)
        if path.name != "result.json":
            raise ConsoleError("FILE_NOT_FOUND", "请选择 result.json", status_code=404)
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ConsoleError("FILE_ENCODING_ERROR", "无法读取 result.json", status_code=400) from exc
        report_path = path.with_name("report.md")
        report_markdown = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
        return {
            "summary": _report_summary(self, path, result),
            "result": result,
            "report_markdown": report_markdown,
        }


def _targets_snapshot(root: Path, profile_dir: Path | None = None) -> list[dict[str, Any]]:
    target_files = sorted((profile_dir or root / "test_workspace" / "targets").glob("*/target.yaml"))
    target_contexts = [load_target_context(path, workspace_root=root) for path in target_files]
    suite_manifests = {
        manifest.resolve(strict=False)
        for context in target_contexts
        for manifest in context.defaults.suite_dir.glob("*/suite.yaml")
    }
    suites_by_binding = _suite_snapshots(root, sorted(suite_manifests))
    result: list[dict[str, Any]] = []
    for target_context in target_contexts:
        modules: list[dict[str, Any]] = []
        module_root = target_context.defaults.module_dir
        for module_file in sorted(module_root.glob("*/module.yaml")) if module_root.exists() else []:
            module_context = load_module_context(target_context, module_file)
            key = (target_context.target, module_context.module)
            assets = [
                _asset(root, module_context.config_path, "CONFIG"),
                _asset(root, module_context.profile_path, "SCAFFOLD"),
                _asset(root, module_context.fixture_path, "SCAFFOLD"),
                _asset(root, module_context.harness_path, "SCAFFOLD"),
            ]
            modules.append({
                "name": module_context.module,
                "module_type": module_context.module_type,
                "diagnostics": module_context.diagnostics,
                "assets": [asset for asset in assets if asset is not None],
                "suites": suites_by_binding.pop(key, []),
            })
        result.append({
            "name": target_context.target,
            "diagnostics": target_context.diagnostics,
            "config_path": _relative(root, target_context.config_path),
            "modules": modules,
        })
    for (target_name, module_name), suites in sorted(suites_by_binding.items()):
        target = next((item for item in result if item["name"] == target_name), None)
        if target is None:
            target = {"name": target_name, "diagnostics": [], "config_path": None, "modules": []}
            result.append(target)
        target["modules"].append({
            "name": module_name,
            "module_type": "",
            "diagnostics": [],
            "assets": [],
            "suites": suites,
        })
    return result


def _suite_snapshots(
    root: Path,
    manifests: list[Path] | None = None,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    suites: dict[tuple[str, str], list[dict[str, Any]]] = {}
    suites_root = root / "test_workspace" / "suites"
    manifest_paths = manifests
    if manifest_paths is None:
        manifest_paths = sorted(suites_root.glob("*/*/suite.yaml")) if suites_root.exists() else []
    for manifest in manifest_paths:
        context = load_suite_context(manifest, workspace_root=root)
        cases: list[dict[str, Any]] = []
        for case_file in context.case_files:
            parsed = parse_suite_case_file(case_file, context.module)
            lines = case_file.read_text(encoding="utf-8").splitlines()
            line_lookup = _case_line_lookup(lines)
            for case in parsed.cases:
                cases.append({
                    "id": case.id,
                    "title": case.title,
                    "priority": case.priority,
                    "source_path": _relative(root, case_file),
                    "source_line": line_lookup.get(case.id),
                })
        assets = [_asset(root, manifest, "CONFIG"), _asset(root, context.profile_path, "SCAFFOLD")]
        assets.extend(_asset(root, path, "CASE") for path in context.case_files)
        item = {
            "name": context.suite,
            "manifest_path": _relative(root, manifest),
            "profile_path": _relative(root, context.profile_path),
            "diagnostics": context.diagnostics,
            "assets": [asset for asset in assets if asset is not None],
            "cases": cases,
        }
        suites.setdefault((context.target, context.module), []).append(item)
    return suites


def _tasks_snapshot(root: Path) -> list[dict[str, Any]]:
    task_root = root / "test_workspace" / "tasks"
    tasks: list[dict[str, Any]] = []
    for path in sorted(task_root.glob("*.yaml")) if task_root.exists() else []:
        context = load_task_context(path, workspace_root=root)
        tasks.append({
            "name": context.task,
            "path": _relative(root, path),
            "description": context.description,
            "unit_count": len(context.units),
            "env_files": [_relative(root, item) for item in context.env_files],
            "diagnostics": context.diagnostics,
        })
    return tasks


def _case_line_lookup(lines: list[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for index, line in enumerate(lines, start=1):
        match = _CASE_HEADER.match(line)
        if match:
            found[match.group(1)] = index
    return found


def _asset(root: Path, path: Path | None, owner: str) -> dict[str, Any] | None:
    if path is None:
        return None
    return {"path": _relative(root, path), "name": path.name, "owner": owner, "exists": path.exists()}


def _relative(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve(strict=False).relative_to(root).as_posix()
    except ValueError:
        return str(path.resolve(strict=False))


def _inside(root: Path, path: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _configured_path(root: Path, configured: Path, label: str) -> Path:
    path = configured if configured.is_absolute() else root / configured
    resolved = path.expanduser().resolve(strict=False)
    if not _inside(root, resolved):
        raise ValueError(f"workspace.paths.{label} must stay inside workspace")
    return resolved


def _workspace_paths(root: Path) -> WorkspacePaths:
    configured = load_workspace_paths(root / AITEST_CONFIG_PATH)
    return WorkspacePaths(
        generated_dir=_configured_path(root, configured.generated_dir, "generated_dir"),
        profile_dir=_configured_path(root, configured.profile_dir, "profile_dir"),
        reports_dir=_configured_path(root, configured.reports_dir, "reports_dir"),
        project_config=root / AITEST_CONFIG_PATH,
    )


def _target_contexts(root: Path, profile_dir: Path) -> list[Any]:
    contexts = [
        load_target_context(path, workspace_root=root)
        for path in sorted(profile_dir.glob("*/target.yaml"))
    ]
    for context in contexts:
        for label, path in (
            ("module_dir", context.defaults.module_dir),
            ("helper_dir", context.defaults.helper_dir),
            ("suite_dir", context.defaults.suite_dir),
            ("generated_dir", context.defaults.generated_dir),
            ("reports_dir", context.defaults.reports_dir),
        ):
            if not _inside(root, path):
                raise ValueError(f"target defaults.{label} must stay inside workspace")
    return contexts


def _unique_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve(strict=False)
        if resolved not in seen:
            unique.append(resolved)
            seen.add(resolved)
    return unique


def _git_branch(root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _report_summary(state: WorkspaceState, path: Path, data: dict[str, Any]) -> dict[str, Any]:
    scope = data.get("run_scope", {}) if isinstance(data.get("run_scope"), dict) else {}
    summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
    return {
        "run_id": str(data.get("run_id", "")),
        "status": str(data.get("status", "UNKNOWN")),
        "timestamp": str(data.get("timestamp", "")),
        "duration_seconds": data.get("duration_seconds", summary.get("duration_seconds", 0)),
        "summary": summary,
        "scope": scope,
        "target": data.get("target", scope.get("target", "")),
        "module": data.get("module", scope.get("module", "")),
        "suite": data.get("suite", scope.get("suite", "")),
        "result_path": state.relative(path),
        "report_path": state.relative(path.with_name("report.md")) if path.with_name("report.md").exists() else None,
    }
