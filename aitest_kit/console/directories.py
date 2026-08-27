from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from aitest_kit.console.errors import ConsoleError


_WORKSPACE_MARKERS = (Path("aitest_config/aitest.yaml"), Path("test_workspace"))


def browse_directories(raw_path: str | None, *, fallback: Path | None = None) -> dict[str, Any]:
    path = _directory_path(raw_path, fallback=fallback)
    try:
        children = [item for item in path.iterdir() if item.is_dir()]
    except OSError as exc:
        raise ConsoleError(
            "DIRECTORY_READ_FAILED",
            f"无法读取目录：{path}",
            status_code=403,
        ) from exc

    visible = sorted(children, key=lambda item: item.name.casefold())
    return {
        "path": str(path),
        "parent": str(path.parent) if path.parent != path else None,
        "initialized": _is_workspace(path),
        "directories": [
            {
                "name": item.name,
                "path": str(item.resolve(strict=False)),
                "initialized": _is_workspace(item),
            }
            for item in visible
        ],
    }


def _directory_path(raw_path: str | None, *, fallback: Path | None) -> Path:
    candidate = Path(raw_path).expanduser() if raw_path and raw_path.strip() else fallback or Path.home()
    path = candidate.resolve(strict=False)
    if not path.exists() or not path.is_dir():
        raise ConsoleError("DIRECTORY_INVALID", f"目录不存在或不是目录：{path}")
    if not os.access(path, os.R_OK | os.X_OK):
        raise ConsoleError("DIRECTORY_READ_FAILED", f"目录不可读：{path}", status_code=403)
    return path


def _is_workspace(path: Path) -> bool:
    return all((path / marker).exists() for marker in _WORKSPACE_MARKERS)
