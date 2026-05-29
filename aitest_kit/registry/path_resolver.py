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


def resolve_path_tree(
    value: Any,
    *,
    base_dir: Path,
    diagnostics: list[str],
    field: str,
) -> Any:
    """Resolve every string leaf in a path-oriented config tree."""
    if isinstance(value, str):
        return resolve_path(value, base_dir=base_dir, diagnostics=diagnostics, field=field)
    if isinstance(value, list):
        return [
            resolve_path_tree(item, base_dir=base_dir, diagnostics=diagnostics, field=f"{field}[]")
            for item in value
        ]
    if isinstance(value, dict):
        return {
            str(key): resolve_path_tree(item, base_dir=base_dir, diagnostics=diagnostics, field=f"{field}.{key}")
            for key, item in value.items()
        }
    return value
