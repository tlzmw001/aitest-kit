"""Workspace initialization and execution helpers."""
from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Iterator


_TEMPLATE_PACKAGE = "aitest_kit.templates.project_workspace"


@dataclass
class InitWorkspaceResult:
    target: Path
    created: int = 0
    overwritten: int = 0
    skipped: int = 0


@contextmanager
def push_workspace(workspace: str | Path | None) -> Iterator[Path]:
    """Temporarily run CLI logic from a workspace root."""
    previous = Path.cwd()
    if workspace is None:
        yield previous
        return

    target = Path(workspace).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"workspace does not exist: {target}")
    if not target.is_dir():
        raise NotADirectoryError(f"workspace is not a directory: {target}")

    os.chdir(target)
    try:
        yield target
    finally:
        os.chdir(previous)


def init_workspace(target: str | Path, *, force: bool = False) -> InitWorkspaceResult:
    """Copy the packaged project workspace template into ``target``."""
    target_path = Path(target).expanduser().resolve()
    template_root = resources.files(_TEMPLATE_PACKAGE)
    result = InitWorkspaceResult(target=target_path)

    conflicts = [
        relative
        for relative in _template_files(template_root)
        if (target_path / relative).exists()
    ]
    if conflicts and not force:
        names = ", ".join(str(item) for item in conflicts[:8])
        if len(conflicts) > 8:
            names += f", ... (+{len(conflicts) - 8} more)"
        raise FileExistsError(
            "target already contains template-managed file(s): "
            f"{names}. Use --force to overwrite them."
        )

    target_path.mkdir(parents=True, exist_ok=True)
    for relative in _template_files(template_root):
        source = template_root.joinpath(*relative.parts)
        destination = target_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        existed = destination.exists()
        destination.write_bytes(source.read_bytes())
        if existed:
            result.overwritten += 1
        else:
            result.created += 1

    return result


def _template_files(root) -> list[Path]:
    files: list[Path] = []
    _collect_template_files(root, Path(), files)
    return sorted(files)


def _collect_template_files(node, relative: Path, files: list[Path]) -> None:
    for child in node.iterdir():
        child_relative = relative / child.name
        if child.is_dir():
            if child.name == "__pycache__":
                continue
            _collect_template_files(child, child_relative, files)
            continue
        if child_relative == Path("__init__.py"):
            continue
        if child.name == ".DS_Store":
            continue
        if child.name.endswith((".pyc", ".pyo")):
            continue
        files.append(child_relative)
