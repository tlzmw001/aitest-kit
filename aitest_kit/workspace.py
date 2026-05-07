"""Workspace helpers for project-template initialization and scoped CLI runs."""
from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Iterator, Protocol


class _TemplateNode(Protocol):
    name: str

    def is_dir(self) -> bool: ...
    def iterdir(self) -> Iterator["_TemplateNode"]: ...
    def read_bytes(self) -> bytes: ...


@dataclass
class InitWorkspaceResult:
    target: Path
    copied_files: list[Path] = field(default_factory=list)
    overwritten_files: list[Path] = field(default_factory=list)


@contextmanager
def push_workspace(workspace: str | Path | None) -> Iterator[Path]:
    """Temporarily run relative-path CLI logic from a workspace root."""
    if workspace is None:
        yield Path.cwd()
        return

    root = Path(workspace).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"workspace does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"workspace is not a directory: {root}")

    previous = Path.cwd()
    os.chdir(root)
    try:
        yield root
    finally:
        os.chdir(previous)


def init_workspace(
    target: str | Path,
    *,
    force: bool = False,
) -> InitWorkspaceResult:
    """Copy the packaged project workspace template into ``target``."""
    target_root = Path(target).expanduser().resolve()
    if target_root.exists() and not target_root.is_dir():
        raise NotADirectoryError(f"target is not a directory: {target_root}")
    target_root.mkdir(parents=True, exist_ok=True)

    template_root = _template_root()
    template_files = list(_iter_template_files(template_root))
    conflicts = [
        rel for rel, _ in template_files
        if (target_root / rel).exists() and not force
    ]
    if conflicts:
        lines = [
            "refusing to overwrite existing files:",
            *[f"- {path.as_posix()}" for path in conflicts[:20]],
        ]
        if len(conflicts) > 20:
            lines.append(f"- ... and {len(conflicts) - 20} more")
        lines.append("rerun with --force to overwrite template-managed files")
        raise FileExistsError("\n".join(lines))

    result = InitWorkspaceResult(target=target_root)
    for rel, src in template_files:
        destination = target_root / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            result.overwritten_files.append(rel)
        destination.write_bytes(src.read_bytes())
        result.copied_files.append(rel)
    return result


def _template_root() -> _TemplateNode:
    dev_template = Path(__file__).resolve().parents[1] / "templates" / "project_workspace"
    if dev_template.exists():
        return dev_template
    return resources.files("aitest_kit.templates").joinpath("project_workspace")


def _iter_template_files(
    root: _TemplateNode,
    prefix: Path = Path(),
) -> Iterator[tuple[Path, _TemplateNode]]:
    for child in root.iterdir():
        rel_path = prefix / child.name
        if child.is_dir():
            yield from _iter_template_files(child, rel_path)
        else:
            yield rel_path, child
