"""Path resolution helpers for registry configuration files."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def expand_env(value: str, diagnostics: list[str], field: str) -> str:
    """Expand ${ENV_NAME} while reporting missing variables."""
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in os.environ:
            missing.append(name)
            return match.group(0)
        return os.environ[name]

    expanded = _ENV_PATTERN.sub(replace, value)
    for name in missing:
        diagnostics.append(f"E700: {field} references undefined environment variable {name}")
    return expanded


def resolve_path(
    value: Any,
    *,
    base_dir: Path,
    diagnostics: list[str],
    field: str,
    must_exist: bool = False,
) -> Path | None:
    """Resolve a config path relative to ``base_dir`` after env expansion."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        diagnostics.append(f"E700: {field} must be a non-empty string")
        return None

    raw = expand_env(value.strip(), diagnostics, field)
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    resolved = path.resolve(strict=False)
    if must_exist and not resolved.exists():
        diagnostics.append(f"E701: {field} path does not exist: {resolved}")
    return resolved


def resolve_named_path(
    value: Any,
    *,
    default_dir: Path,
    workspace_root: Path,
    diagnostics: list[str],
    field: str,
    must_exist: bool = False,
) -> Path | None:
    """Resolve a path, treating bare filenames as relative to ``default_dir``."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        diagnostics.append(f"E700: {field} must be a non-empty string")
        return None

    expanded = expand_env(value.strip(), diagnostics, field)
    path = Path(expanded).expanduser()
    if not path.is_absolute():
        base_dir = default_dir if len(path.parts) == 1 else workspace_root
        path = base_dir / path
    resolved = path.resolve(strict=False)
    if must_exist and not resolved.exists():
        diagnostics.append(f"E701: {field} path does not exist: {resolved}")
    return resolved


def resolve_knowledge_refs(
    value: Any,
    *,
    base_dir: Path,
    diagnostics: list[str],
    field: str,
) -> dict[str, list[Path]]:
    """Resolve knowledge reference config into ``key -> list[Path]``.

    ``knowledge_refs`` accepts a file path, a directory path, or a list of
    file/directory paths for each top-level key. Existing directories expand to
    their direct ``*.md`` children. Missing paths are kept unresolved so codegen
    can preserve metadata without turning documentation availability into a hard
    generation prerequisite.
    """
    if value is None:
        return {}
    if not isinstance(value, dict):
        diagnostics.append(f"E700: {field} must be a mapping")
        return {}

    resolved: dict[str, list[Path]] = {}
    for key, raw_refs in value.items():
        ref_key = str(key)
        paths = _resolve_knowledge_ref_values(
            raw_refs,
            base_dir=base_dir,
            diagnostics=diagnostics,
            field=f"{field}.{ref_key}",
        )
        if paths:
            resolved[ref_key] = _dedupe_paths(paths)
    return resolved


def merge_knowledge_refs(*refs: dict[str, Any]) -> dict[str, list[Path]]:
    """Merge already-resolved knowledge refs while preserving order."""
    merged: dict[str, list[Path]] = {}
    for ref_map in refs:
        if not isinstance(ref_map, dict):
            continue
        for key, raw_paths in ref_map.items():
            paths = raw_paths if isinstance(raw_paths, list) else [raw_paths]
            bucket = merged.setdefault(str(key), [])
            for path in paths:
                if isinstance(path, Path) and path not in bucket:
                    bucket.append(path)
    return {key: values for key, values in merged.items() if values}


def _resolve_knowledge_ref_values(
    value: Any,
    *,
    base_dir: Path,
    diagnostics: list[str],
    field: str,
) -> list[Path]:
    if isinstance(value, str):
        path = resolve_path(value, base_dir=base_dir, diagnostics=diagnostics, field=field)
        return _expand_knowledge_path(path)
    if isinstance(value, list):
        paths: list[Path] = []
        for index, item in enumerate(value):
            paths.extend(
                _resolve_knowledge_ref_values(
                    item,
                    base_dir=base_dir,
                    diagnostics=diagnostics,
                    field=f"{field}[{index}]",
                )
            )
        return paths
    diagnostics.append(f"E700: {field} must be a path string or list of path strings")
    return []


def _expand_knowledge_path(path: Path | None) -> list[Path]:
    if path is None:
        return []
    if path.exists() and path.is_dir():
        return sorted(item.resolve(strict=False) for item in path.glob("*.md"))
    return [path]


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    for path in paths:
        if path not in result:
            result.append(path)
    return result
