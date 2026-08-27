from __future__ import annotations

import keyword
import os
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from aitest_kit.codegen.project_config import FALLBACK_PROJECT_CONFIG_DATA
from aitest_kit.console.errors import ConsoleError
from aitest_kit.console.workspace import WorkspaceState
from aitest_kit.registry import (
    load_module_context,
    load_suite_context,
    load_target_context,
    load_task_context,
)


_PYTHON_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ASSET_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


class AssetService:
    def __init__(self, workspace: WorkspaceState) -> None:
        self.workspace = workspace

    def module_types(self) -> list[dict[str, str]]:
        config = _read_yaml(self.workspace.paths.project_config, "workspace config")
        codegen = config.get("codegen") if isinstance(config.get("codegen"), dict) else {}
        raw = codegen.get("module_types")
        module_types = raw if isinstance(raw, dict) else FALLBACK_PROJECT_CONFIG_DATA["module_types"]
        return [
            {
                "name": str(name),
                "description": str(value.get("description", "")) if isinstance(value, dict) else "",
            }
            for name, value in module_types.items()
        ]

    def create_target(self, *, name: str, source_root: str = "") -> dict[str, Any]:
        _validate_name(name, python_name=True)
        root = self.workspace.root
        target_dir = self.workspace.paths.profile_dir / name
        paths = [
            target_dir,
            root / "test_workspace" / "suites" / name,
            self.workspace.paths.generated_dir / name,
            self.workspace.paths.reports_dir / name,
        ]
        _require_paths_absent(paths)
        data: dict[str, Any] = {
            "target": name,
            "defaults": {
                "module_dir": _relative(root, target_dir / "modules"),
                "helper_dir": _relative(root, target_dir / "helpers"),
                "suite_dir": _relative(root, paths[1]),
                "generated_dir": _relative(root, paths[2]),
                "reports_dir": _relative(root, paths[3]),
            },
        }
        if source_root.strip():
            data["source_root"] = str(Path(source_root).expanduser().resolve(strict=False))
        try:
            for path in paths:
                path.mkdir(parents=True, exist_ok=False)
            (target_dir / "modules").mkdir()
            (target_dir / "helpers").mkdir()
            (target_dir / "target.yaml").write_text(_dump_yaml(data), encoding="utf-8")
            context = load_target_context(target_dir / "target.yaml", workspace_root=root)
            _raise_diagnostics(context.diagnostics)
        except ConsoleError:
            _rollback_paths(paths)
            raise
        except (OSError, ValueError, RuntimeError) as exc:
            _rollback_paths(paths)
            raise ConsoleError("ASSET_CREATE_FAILED", "创建 target 失败", status_code=500) from exc
        return self.workspace.snapshot()

    def create_module(self, *, target: str, name: str, module_type: str) -> dict[str, Any]:
        _validate_name(target, python_name=True)
        _validate_name(name, python_name=True)
        allowed = {item["name"] for item in self.module_types()}
        if module_type not in allowed:
            raise ConsoleError("MODULE_TYPE_INVALID", f"未知 module_type：{module_type}")
        target_context = self._target(target)
        package_dir = target_context.defaults.module_dir / name
        _require_paths_absent([package_dir])
        class_name = "".join(part.capitalize() for part in name.split("_")) + "Harness"
        try:
            package_dir.mkdir(parents=True)
            (package_dir / "__init__.py").write_text("", encoding="utf-8")
            (package_dir / "module.yaml").write_text(
                _dump_yaml({
                    "target": target,
                    "module": name,
                    "module_type": module_type,
                    "registered_suites": [],
                }),
                encoding="utf-8",
            )
            (package_dir / "profile.md").write_text(f"# {name} module profile\n", encoding="utf-8")
            (package_dir / "harness.py").write_text(
                f'class {class_name}:\n    """Add real {name} test capabilities here."""\n\n'
                "    def close(self) -> None:\n        pass\n",
                encoding="utf-8",
            )
            (package_dir / "fixture.py").write_text(
                "import pytest\n\n"
                f"from .harness import {class_name}\n\n\n"
                "@pytest.fixture\n"
                f"def setup_{name}() -> {class_name}:\n"
                f"    harness = {class_name}()\n"
                "    try:\n        yield harness\n"
                "    finally:\n        harness.close()\n",
                encoding="utf-8",
            )
            context = load_module_context(target_context, package_dir / "module.yaml")
            _raise_diagnostics(context.diagnostics)
        except ConsoleError:
            shutil.rmtree(package_dir, ignore_errors=True)
            raise
        except (OSError, ValueError, RuntimeError) as exc:
            shutil.rmtree(package_dir, ignore_errors=True)
            raise ConsoleError("ASSET_CREATE_FAILED", "创建 module 失败", status_code=500) from exc
        return self.workspace.snapshot()

    def create_suite(
        self,
        *,
        target: str,
        module: str,
        name: str,
        register: bool = True,
    ) -> dict[str, Any]:
        _validate_name(target, python_name=True)
        _validate_name(module, python_name=True)
        _validate_name(name)
        target_context = self._target(target)
        module_context = self._module(target_context, module)
        suite_dir = target_context.defaults.suite_dir / name
        _require_paths_absent([suite_dir])
        module_before = module_context.config_path.read_text(encoding="utf-8")
        try:
            suite_dir.mkdir(parents=True)
            manifest = suite_dir / "suite.yaml"
            manifest.write_text(
                _dump_yaml({"target": target, "module": module, "suite": name, "case_files": ["cases.md"]}),
                encoding="utf-8",
            )
            (suite_dir / "cases.md").write_text(
                f"# {name}\n\n在此文件中新增、修改或删除 Markdown case。\n",
                encoding="utf-8",
            )
            (suite_dir / f"profile_{name}_suite.md").write_text(
                f"# profile_{name}_suite\n\n```yaml\nprofile_scope: case_suite\n"
                f"parent_module: {module}\nsuite: {name}\n```\n",
                encoding="utf-8",
            )
            context = load_suite_context(manifest, workspace_root=self.workspace.root)
            _raise_diagnostics(context.diagnostics)
            if register:
                self._register_suite(module_context.config_path, context.suite, context.manifest_path)
                reloaded = load_module_context(target_context, module_context.config_path)
                _raise_diagnostics(reloaded.diagnostics)
        except ConsoleError:
            shutil.rmtree(suite_dir, ignore_errors=True)
            module_context.config_path.write_text(module_before, encoding="utf-8")
            raise
        except (OSError, ValueError, RuntimeError) as exc:
            shutil.rmtree(suite_dir, ignore_errors=True)
            module_context.config_path.write_text(module_before, encoding="utf-8")
            raise ConsoleError("ASSET_CREATE_FAILED", "创建 suite 失败", status_code=500) from exc
        return self.workspace.snapshot()

    def create_task(self, *, name: str, description: str, suite_files: list[str]) -> dict[str, Any]:
        _validate_name(name)
        if not suite_files:
            raise ConsoleError("ASSET_VALIDATION_FAILED", "task 至少需要一个 suite")
        task_path = self.workspace.root / "test_workspace" / "tasks" / f"{name}.yaml"
        _require_paths_absent([task_path])
        suites = []
        seen: set[Path] = set()
        for raw_path in suite_files:
            path = self.workspace.resolve_inside(raw_path)
            context = load_suite_context(path, workspace_root=self.workspace.root)
            _raise_diagnostics(context.diagnostics)
            resolved = context.manifest_path.resolve(strict=False)
            if resolved not in seen:
                suites.append(context)
                seen.add(resolved)
        units = [
            {
                "name": suite.suite,
                "target": suite.target,
                "module": suite.module,
                "suite": suite.suite,
                "suite_file": Path(os.path.relpath(suite.manifest_path, task_path.parent)).as_posix(),
            }
            for suite in suites
        ]
        try:
            task_path.parent.mkdir(parents=True, exist_ok=True)
            task_path.write_text(
                _dump_yaml({"schema_version": 1, "task": name, "description": description, "units": units}),
                encoding="utf-8",
            )
            context = load_task_context(task_path, workspace_root=self.workspace.root)
            _raise_diagnostics(context.diagnostics)
        except ConsoleError:
            task_path.unlink(missing_ok=True)
            raise
        except (OSError, ValueError, RuntimeError) as exc:
            task_path.unlink(missing_ok=True)
            raise ConsoleError("ASSET_CREATE_FAILED", "创建 task 失败", status_code=500) from exc
        return self.workspace.snapshot()

    def _target(self, name: str) -> Any:
        path = self.workspace.paths.profile_dir / name / "target.yaml"
        if not path.exists():
            raise ConsoleError("ASSET_PARENT_NOT_FOUND", f"target 不存在：{name}", status_code=404)
        context = load_target_context(path, workspace_root=self.workspace.root)
        _raise_diagnostics(context.diagnostics)
        return context

    def _module(self, target_context: Any, name: str) -> Any:
        path = target_context.defaults.module_dir / name / "module.yaml"
        if not path.exists():
            raise ConsoleError("ASSET_PARENT_NOT_FOUND", f"module 不存在：{name}", status_code=404)
        context = load_module_context(target_context, path)
        _raise_diagnostics(context.diagnostics)
        return context

    def _register_suite(self, module_path: Path, suite: str, manifest: Path) -> None:
        data = _read_yaml(module_path, "module")
        registered = data.get("registered_suites") or []
        if not isinstance(registered, list):
            raise ConsoleError("ASSET_VALIDATION_FAILED", "module registered_suites 必须是 list")
        registered.append({
            "suite": suite,
            "manifest": _relative(self.workspace.root, manifest),
            "status": "active",
        })
        data["registered_suites"] = registered
        module_path.write_text(_dump_yaml(data), encoding="utf-8")


def _validate_name(name: str, *, python_name: bool = False) -> None:
    valid = _PYTHON_NAME.fullmatch(name) if python_name else _ASSET_NAME.fullmatch(name)
    if not valid or (python_name and keyword.iskeyword(name)):
        rule = "Python 标识符" if python_name else "字母、数字、_ 或 -"
        raise ConsoleError("ASSET_NAME_INVALID", f"名称必须是{rule}：{name}")


def _require_paths_absent(paths: list[Path]) -> None:
    existing = next((path for path in paths if path.exists()), None)
    if existing is not None:
        raise ConsoleError("ASSET_ALREADY_EXISTS", f"资产路径已存在：{existing}", status_code=409)


def _raise_diagnostics(diagnostics: list[str]) -> None:
    errors = [item for item in diagnostics if item.lstrip().startswith("E")]
    if errors:
        raise ConsoleError("ASSET_VALIDATION_FAILED", "; ".join(errors))


def _read_yaml(path: Path, label: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ConsoleError("ASSET_VALIDATION_FAILED", f"无法读取 {label} YAML：{path}") from exc
    if not isinstance(data, dict):
        raise ConsoleError("ASSET_VALIDATION_FAILED", f"{label} YAML 根节点必须是 mapping")
    return data


def _dump_yaml(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def _relative(base: Path, path: Path) -> str:
    return path.resolve(strict=False).relative_to(base.resolve(strict=False)).as_posix()


def _rollback_paths(paths: list[Path]) -> None:
    for path in reversed(paths):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink(missing_ok=True)
