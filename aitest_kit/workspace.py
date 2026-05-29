"""Workspace initialization and execution helpers."""
from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from importlib import resources
from pathlib import Path
from typing import Iterator


_TEMPLATE_PACKAGE = "aitest_kit.templates.project_workspace"
_WORKSPACE_METADATA = Path(".aitest/workspace.json")
_METADATA_SCHEMA_VERSION = 1

_MANUAL_EXACT_PATHS = {
    "aitest_config/aitest.yaml",
    "test_workspace/knowledge/L0_system_architecture.md",
    "test_workspace/knowledge/TEST_SPEC.md",
}
_MANUAL_PREFIXES = (
    "test_workspace/knowledge/L1/",
    "test_workspace/knowledge/L2/",
)
@dataclass
class InitWorkspaceResult:
    target: Path
    created: int = 0
    overwritten: int = 0
    skipped: int = 0


@dataclass
class UpgradeEntry:
    relative: Path
    status: str
    message: str


@dataclass
class UpgradeWorkspaceResult:
    target: Path
    applied: bool
    entries: list[UpgradeEntry]
    created: int = 0
    updated: int = 0
    skipped: int = 0
    backup_dir: Path | None = None

    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in self.entries:
            counts[entry.status] = counts.get(entry.status, 0) + 1
        return counts


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

    _write_workspace_metadata(
        target_path,
        template_hashes=_template_hashes(template_root),
        created_at=_now_utc(),
    )
    return result


def upgrade_workspace(
    target: str | Path,
    *,
    apply: bool = False,
    force_files: set[str] | None = None,
) -> UpgradeWorkspaceResult:
    """Check or apply safe upgrades from the packaged workspace template."""
    target_path = Path(target).expanduser().resolve()
    if not target_path.exists():
        raise FileNotFoundError(f"workspace does not exist: {target_path}")
    if not target_path.is_dir():
        raise NotADirectoryError(f"workspace is not a directory: {target_path}")

    force_paths = {Path(item).as_posix().lstrip("./") for item in force_files or set()}
    template_root = resources.files(_TEMPLATE_PACKAGE)
    template_hashes = _template_hashes(template_root)
    metadata_doc = _read_workspace_metadata(target_path)
    previous_hashes = _metadata_hashes(metadata_doc)
    created_at = str(metadata_doc.get("created_at") or _now_utc())

    entries: list[UpgradeEntry] = []
    result = UpgradeWorkspaceResult(target=target_path, applied=apply, entries=entries)
    synced_hashes: dict[str, str] = {}
    backup_dir: Path | None = None

    for relative in _template_files(template_root):
        key = relative.as_posix()
        destination = target_path / relative
        new_hash = template_hashes[key]
        source = template_root.joinpath(*relative.parts)

        entry = _classify_template_file(
            relative=relative,
            destination=destination,
            new_hash=new_hash,
            previous_hash=previous_hashes.get(key),
            force_paths=force_paths,
        )
        entries.append(entry)

        if entry.status == "OK":
            synced_hashes[key] = new_hash
            continue

        if not apply:
            continue

        if entry.status == "NEW":
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
            result.created += 1
            synced_hashes[key] = new_hash
            continue

        if entry.status in {"UPDATE", "FORCE"}:
            if destination.exists():
                if backup_dir is None:
                    backup_dir = _new_backup_dir(target_path)
                _backup_file(target_path, destination, backup_dir)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
            result.updated += 1
            synced_hashes[key] = new_hash
            continue

        result.skipped += 1

    for key in sorted(set(previous_hashes) - set(template_hashes)):
        entries.append(UpgradeEntry(relative=Path(key), status="OBSOLETE", message="not present in current template; kept"))

    if apply:
        merged_hashes = dict(previous_hashes)
        merged_hashes.update(synced_hashes)
        for key in set(previous_hashes) - set(template_hashes):
            merged_hashes.pop(key, None)
        _write_workspace_metadata(
            target_path,
            template_hashes=merged_hashes,
            created_at=created_at,
            backup_dir=backup_dir,
        )
        result.backup_dir = backup_dir

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


def _classify_template_file(
    *,
    relative: Path,
    destination: Path,
    new_hash: str,
    previous_hash: str | None,
    force_paths: set[str],
) -> UpgradeEntry:
    key = relative.as_posix()
    if key in force_paths:
        return UpgradeEntry(relative=relative, status="FORCE", message="selected by --force-file")
    if not destination.exists():
        if _is_manual_path(key):
            return UpgradeEntry(relative=relative, status="MANUAL", message="project-owned template file is missing")
        return UpgradeEntry(relative=relative, status="NEW", message="missing template file")

    current_hash = _sha256_path(destination)
    if current_hash == new_hash:
        return UpgradeEntry(relative=relative, status="OK", message="up to date")
    if _is_manual_path(key):
        return UpgradeEntry(relative=relative, status="MANUAL", message="project-owned file differs; review manually")
    if previous_hash and current_hash == previous_hash:
        return UpgradeEntry(relative=relative, status="UPDATE", message="safe template update")
    if previous_hash:
        return UpgradeEntry(relative=relative, status="LOCAL", message="local modifications detected; skipped")
    return UpgradeEntry(relative=relative, status="LOCAL", message="no workspace manifest hash; review manually")


def _is_manual_path(key: str) -> bool:
    if key in _MANUAL_EXACT_PATHS:
        return True
    return any(key.startswith(prefix) for prefix in _MANUAL_PREFIXES)


def _template_hashes(root) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative in _template_files(root):
        source = root.joinpath(*relative.parts)
        hashes[relative.as_posix()] = _sha256_bytes(source.read_bytes())
    return hashes


def _read_workspace_metadata(target: Path) -> dict:
    metadata_path = target / _WORKSPACE_METADATA
    if not metadata_path.exists():
        return {}
    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _metadata_hashes(data: dict) -> dict[str, str]:
    raw_files = data.get("template_files")
    if not isinstance(raw_files, dict):
        return {}
    hashes: dict[str, str] = {}
    for path, value in raw_files.items():
        if isinstance(value, str):
            hashes[str(path)] = value
        elif isinstance(value, dict) and isinstance(value.get("sha256"), str):
            hashes[str(path)] = value["sha256"]
    return hashes


def _write_workspace_metadata(
    target: Path,
    *,
    template_hashes: dict[str, str],
    created_at: str,
    backup_dir: Path | None = None,
) -> None:
    metadata_path = target / _WORKSPACE_METADATA
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schema_version": _METADATA_SCHEMA_VERSION,
        "aitest_kit_version": _aitest_kit_version(),
        "template_version": _aitest_kit_version(),
        "created_at": created_at,
        "updated_at": _now_utc(),
        "template_files": {path: {"sha256": sha} for path, sha in sorted(template_hashes.items())},
    }
    if backup_dir is not None:
        document["last_backup_dir"] = str(backup_dir.relative_to(target))
    metadata_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _new_backup_dir(target: Path) -> Path:
    base = target / ".aitest" / "backups"
    timestamp = datetime.now(timezone.utc).strftime("upgrade-%Y%m%d-%H%M%S")
    backup_dir = base / timestamp
    suffix = 1
    while backup_dir.exists():
        backup_dir = base / f"{timestamp}-{suffix}"
        suffix += 1
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def _backup_file(target: Path, source: Path, backup_dir: Path) -> None:
    relative = source.relative_to(target)
    backup_path = backup_dir / relative
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_bytes(source.read_bytes())


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _aitest_kit_version() -> str:
    try:
        return metadata.version("aitest-kit")
    except metadata.PackageNotFoundError:
        return "0+unknown"
