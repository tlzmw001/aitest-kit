from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from aitest_kit.console.errors import ConsoleError
from aitest_kit.console.workspace import WorkspaceState
from aitest_kit.registry import load_module_context, load_suite_context, load_target_context, load_task_context


_LOGGER = logging.getLogger(__name__)

class TrashService:
    def __init__(self, workspace: WorkspaceState) -> None:
        self.workspace = workspace

    def preview(self, identity: dict[str, str]) -> dict[str, Any]:
        kind, normalized, source, modified, blockers = self._resolve(identity)
        return {
            "kind": kind,
            "identity": normalized,
            "paths": [self.workspace.relative(source)],
            "modified_files": [self.workspace.relative(path) for path in modified],
            "blockers": blockers,
            "can_delete": not blockers,
            "recoverable": True,
            "message": "资产会移动到当前 workspace 的 .aitest/trash，可从 Console 恢复。",
        }

    def delete(self, identity: dict[str, str], *, confirmed: bool) -> dict[str, Any]:
        if not confirmed:
            raise ConsoleError(
                "ASSET_DELETE_CONFIRMATION_REQUIRED",
                "删除资产需要明确确认",
                status_code=403,
            )
        preview = self.preview(identity)
        if preview["blockers"]:
            raise ConsoleError("ASSET_DELETE_BLOCKED", "；".join(preview["blockers"]), status_code=409)

        _, _, source, modified, _ = self._resolve(identity)
        entry_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
        entry = self._trash_root / entry_id
        asset_destination = entry / "assets" / self.workspace.relative(source)
        backups: dict[str, str] = {}
        post_hashes: dict[str, str] = {}
        try:
            for path in modified:
                relative = self.workspace.relative(path)
                backup = entry / "backups" / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, backup)
                backups[relative] = relative
            asset_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(asset_destination))
            if preview["kind"] == "suite":
                module_path = modified[0]
                self._unregister_suite(module_path, preview["identity"]["suite"])
                post_hashes[self.workspace.relative(module_path)] = _sha256(module_path)
            manifest = {
                "entry_id": entry_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "kind": preview["kind"],
                "identity": preview["identity"],
                "paths": preview["paths"],
                "backups": backups,
                "post_delete_sha256": post_hashes,
            }
            (entry / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            snapshot = self.workspace.snapshot()
        except Exception as exc:
            self._rollback_delete(entry, source, asset_destination, modified)
            if isinstance(exc, ConsoleError):
                raise
            raise ConsoleError("ASSET_DELETE_FAILED", "删除资产失败，已尝试恢复原状态", status_code=500) from exc
        return {"entry": manifest, "workspace": snapshot}

    def list(self) -> list[dict[str, Any]]:
        if not self._trash_root.exists():
            return []
        result: list[dict[str, Any]] = []
        for manifest_path in sorted(self._trash_root.glob("*/manifest.json"), reverse=True):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                _LOGGER.warning("Ignoring unreadable Console trash manifest: %s", manifest_path, exc_info=True)
                continue
            if isinstance(manifest, dict):
                result.append(manifest)
        return result

    def restore(self, entry_id: str) -> dict[str, Any]:
        if not entry_id or "/" in entry_id or "\\" in entry_id or entry_id in {".", ".."}:
            raise ConsoleError("TRASH_ENTRY_NOT_FOUND", "回收站条目不存在", status_code=404)
        entry = self._trash_root / entry_id
        manifest_path = entry / "manifest.json"
        if not manifest_path.is_file():
            raise ConsoleError("TRASH_ENTRY_NOT_FOUND", "回收站条目不存在", status_code=404)
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConsoleError("TRASH_RESTORE_FAILED", "回收站 manifest 无法读取") from exc

        paths = manifest.get("paths", [])
        if not isinstance(paths, list) or len(paths) != 1 or not isinstance(paths[0], str):
            raise ConsoleError("TRASH_RESTORE_FAILED", "回收站 manifest 路径无效")
        destination = self.workspace.resolve_inside(paths[0], allow_missing=True)
        trashed_asset = entry / "assets" / paths[0]
        if destination.exists():
            raise ConsoleError("TRASH_RESTORE_CONFLICT", f"恢复目标已存在：{paths[0]}", status_code=409)
        if not trashed_asset.exists():
            raise ConsoleError("TRASH_RESTORE_FAILED", "回收站资产缺失")

        post_hashes = manifest.get("post_delete_sha256", {})
        if not isinstance(post_hashes, dict):
            raise ConsoleError("TRASH_RESTORE_FAILED", "回收站 hash 信息无效")
        for relative, expected in post_hashes.items():
            current = self.workspace.resolve_inside(relative)
            if _sha256(current) != expected:
                raise ConsoleError(
                    "TRASH_RESTORE_CONFLICT",
                    f"删除后 registry 已被修改，拒绝覆盖：{relative}",
                    status_code=409,
                )

        current_registry: dict[Path, bytes] = {}
        moved = False
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(trashed_asset), str(destination))
            moved = True
            backups = manifest.get("backups", {})
            if not isinstance(backups, dict):
                raise ValueError("invalid backups")
            for relative in backups:
                target = self.workspace.resolve_inside(relative)
                current_registry[target] = target.read_bytes()
                backup = entry / "backups" / relative
                target.write_bytes(backup.read_bytes())
            self.workspace.snapshot()
        except Exception as exc:
            for path, content in current_registry.items():
                path.write_bytes(content)
            if moved and destination.exists():
                trashed_asset.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destination), str(trashed_asset))
            if isinstance(exc, ConsoleError):
                raise
            raise ConsoleError("TRASH_RESTORE_FAILED", "恢复失败，已尝试保持回收站状态", status_code=500) from exc
        shutil.rmtree(entry)
        return self.workspace.snapshot()

    @property
    def _trash_root(self) -> Path:
        return self.workspace.root / ".aitest" / "trash"

    def _resolve(
        self,
        identity: dict[str, str],
    ) -> tuple[str, dict[str, str], Path, list[Path], list[str]]:
        kind = str(identity.get("kind", "")).strip()
        if kind == "target":
            return self._target(identity)
        if kind == "module":
            return self._module(identity)
        if kind == "suite":
            return self._suite(identity)
        if kind == "task":
            return self._task(identity)
        raise ConsoleError("ASSET_VALIDATION_FAILED", f"不支持的资产类型：{kind}")

    def _target(self, identity: dict[str, str]) -> tuple[str, dict[str, str], Path, list[Path], list[str]]:
        name = _required(identity, "target")
        source = self.workspace.paths.profile_dir / name
        config = source / "target.yaml"
        if not config.exists():
            raise ConsoleError("ASSET_NOT_FOUND", f"target 不存在：{name}", status_code=404)
        context = load_target_context(config, workspace_root=self.workspace.root)
        _identity(context.target, name)
        module_files = list(context.defaults.module_dir.glob("*/module.yaml"))
        suite_files = list(context.defaults.suite_dir.glob("*/suite.yaml"))
        blockers = ["target 配置存在错误，无法安全删除"] if _has_errors(context.diagnostics) else []
        if module_files:
            blockers.append("target 下仍有 module")
        if suite_files:
            blockers.append("target 下仍有 suite")
        return "target", {"kind": "target", "target": name}, source, [], blockers

    def _module(self, identity: dict[str, str]) -> tuple[str, dict[str, str], Path, list[Path], list[str]]:
        target_name = _required(identity, "target")
        module_name = _required(identity, "module")
        target = self._load_target(target_name)
        source = target.defaults.module_dir / module_name
        config = source / "module.yaml"
        if not config.exists():
            raise ConsoleError("ASSET_NOT_FOUND", f"module 不存在：{module_name}", status_code=404)
        module = load_module_context(target, config)
        _identity(module.module, module_name)
        blockers = ["module 配置存在错误，无法安全删除"] if _has_errors(module.diagnostics) else []
        owned: list[Path] = []
        for path in target.defaults.suite_dir.glob("*/suite.yaml"):
            suite = load_suite_context(path, workspace_root=self.workspace.root)
            if _has_errors(suite.diagnostics):
                blockers.append(f"suite {path.parent.name} 无法安全解析")
            elif (suite.target, suite.module) == (target_name, module_name):
                owned.append(path)
        if owned or module.registered_suites:
            blockers.append("module 下仍有 suite")
        return "module", {"kind": "module", "target": target_name, "module": module_name}, source, [], blockers

    def _suite(self, identity: dict[str, str]) -> tuple[str, dict[str, str], Path, list[Path], list[str]]:
        target_name = _required(identity, "target")
        module_name = _required(identity, "module")
        suite_name = _required(identity, "suite")
        target = self._load_target(target_name)
        module_path = target.defaults.module_dir / module_name / "module.yaml"
        if not module_path.exists():
            raise ConsoleError("ASSET_NOT_FOUND", f"module 不存在：{module_name}", status_code=404)
        source = target.defaults.suite_dir / suite_name
        manifest = source / "suite.yaml"
        if not manifest.exists():
            raise ConsoleError("ASSET_NOT_FOUND", f"suite 不存在：{suite_name}", status_code=404)
        suite = load_suite_context(manifest, workspace_root=self.workspace.root)
        _identity(suite.target, target_name)
        _identity(suite.module, module_name)
        _identity(suite.suite, suite_name)
        blockers = ["suite 配置存在错误，无法安全删除"] if _has_errors(suite.diagnostics) else []
        blockers.extend(self._task_references(manifest))
        normalized = {"kind": "suite", "target": target_name, "module": module_name, "suite": suite_name}
        return "suite", normalized, source, [module_path], blockers

    def _task(self, identity: dict[str, str]) -> tuple[str, dict[str, str], Path, list[Path], list[str]]:
        name = _required(identity, "task")
        source = self.workspace.root / "test_workspace" / "tasks" / f"{name}.yaml"
        if not source.exists():
            raise ConsoleError("ASSET_NOT_FOUND", f"task 不存在：{name}", status_code=404)
        task = load_task_context(source, workspace_root=self.workspace.root)
        _identity(task.task, name)
        blockers = ["task 配置存在错误，无法安全删除"] if _has_errors(task.diagnostics) else []
        return "task", {"kind": "task", "task": name}, source, [], blockers

    def _load_target(self, name: str) -> Any:
        config = self.workspace.paths.profile_dir / name / "target.yaml"
        if not config.exists():
            raise ConsoleError("ASSET_NOT_FOUND", f"target 不存在：{name}", status_code=404)
        target = load_target_context(config, workspace_root=self.workspace.root)
        _identity(target.target, name)
        return target

    def _task_references(self, manifest: Path) -> list[str]:
        task_root = self.workspace.root / "test_workspace" / "tasks"
        references: list[str] = []
        for task_path in sorted(task_root.glob("*.yaml")) if task_root.exists() else []:
            task = load_task_context(task_path, workspace_root=self.workspace.root)
            if task.diagnostics:
                references.append(f"task {task_path.stem} 无法安全解析")
                continue
            if any(unit.suite_file and unit.suite_file.resolve(strict=False) == manifest.resolve(strict=False) for unit in task.units):
                references.append(f"suite 被 task {task.task} 引用")
        return references

    def _unregister_suite(self, module_path: Path, suite_name: str) -> None:
        data = _read_yaml(module_path)
        registered = data.get("registered_suites") or []
        if not isinstance(registered, list):
            raise ConsoleError("ASSET_VALIDATION_FAILED", "module registered_suites 必须是 list")
        filtered = [item for item in registered if _registered_name(item) != suite_name]
        data["registered_suites"] = filtered
        module_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def _rollback_delete(self, entry: Path, source: Path, asset_destination: Path, modified: list[Path]) -> None:
        for path in modified:
            backup = entry / "backups" / self.workspace.relative(path)
            if backup.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, path)
        if asset_destination.exists() and not source.exists():
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(asset_destination), str(source))
        shutil.rmtree(entry, ignore_errors=True)


def _required(identity: dict[str, str], field: str) -> str:
    value = str(identity.get(field, "")).strip()
    if not value or "/" in value or "\\" in value or value in {".", ".."}:
        raise ConsoleError("ASSET_NAME_INVALID", f"无效 {field} 名称")
    return value


def _identity(actual: str, expected: str) -> None:
    if actual != expected:
        raise ConsoleError("ASSET_VALIDATION_FAILED", f"资产身份不一致：期望 {expected}，实际 {actual}")


def _registered_name(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("suite", ""))
    if isinstance(item, str):
        return Path(item).parent.name
    return ""


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ConsoleError("ASSET_VALIDATION_FAILED", f"无法读取 YAML：{path}") from exc
    if not isinstance(data, dict):
        raise ConsoleError("ASSET_VALIDATION_FAILED", f"YAML 根节点必须是 mapping：{path}")
    return data


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _has_errors(diagnostics: list[str]) -> bool:
    return any(item.lstrip().startswith("E") for item in diagnostics)
