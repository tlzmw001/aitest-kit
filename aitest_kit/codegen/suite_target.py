"""Target-aware suite codegen adapters."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from aitest_kit.codegen.project_config import ProjectConfig
from aitest_kit.codegen.suite import SuiteContext


def project_config_for_suite_target(context: SuiteContext, project: ProjectConfig) -> ProjectConfig:
    """Override helper imports for target-aware suites when target helpers exist."""
    if not context.target:
        return project

    from aitest_kit.registry.loader import load_target_context

    target_context = load_target_context(context.target)
    if target_context.config_path is None:
        return project

    updates: dict[str, str] = {}
    helper_dir = target_context.defaults.helper_dir
    http_import = _target_helper_import(
        helper_dir,
        module_name="http",
        import_clause="http as http_helper",
        workspace_root=target_context.workspace_root,
    )
    if http_import:
        updates["helper_import"] = http_import
    grpc_import = _target_helper_import(
        helper_dir,
        module_name="grpc_ops",
        import_clause="grpc_ops",
        workspace_root=target_context.workspace_root,
    )
    if grpc_import:
        updates["grpc_helper_import"] = grpc_import
    return replace(project, **updates) if updates else project


def _target_helper_import(
    helper_dir: Path,
    *,
    module_name: str,
    import_clause: str,
    workspace_root: Path,
) -> str:
    helper_file = helper_dir / f"{module_name}.py"
    if not helper_file.exists():
        return ""
    try:
        relative = helper_dir.resolve(strict=False).relative_to(
            workspace_root.resolve(strict=False)
        )
    except ValueError:
        return ""
    dotted_path = _dotted_import_path(relative)
    return f"from {dotted_path} import {import_clause}" if dotted_path else ""


def _dotted_import_path(path: Path) -> str:
    parts = list(path.parts)
    if not parts or not all(part.isidentifier() for part in parts):
        return ""
    return ".".join(parts)
