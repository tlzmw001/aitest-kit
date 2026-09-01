"""Deterministic Pi Worker runtime seed generation and validation."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping


SEED_SCHEMA_VERSION = 1
RUNTIME_NAME = "pi"
MANIFEST_NAME = "runtime-manifest.json"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class RuntimeSeedError(RuntimeError):
    """Raised when the packaged runtime seed is missing or inconsistent."""


def source_files(source_dir: str | Path) -> tuple[str, ...]:
    root = Path(source_dir)
    files = ["package.json", "package-lock.json"]
    files.extend(path.relative_to(root).as_posix() for path in sorted((root / "src").glob("*.ts")))
    if "src/worker.ts" not in files:
        raise RuntimeSeedError(f"Pi Worker entrypoint is missing under {root}")
    return tuple(files)


def build_runtime_seed(source_dir: str | Path, target_dir: str | Path) -> dict[str, Any]:
    source = Path(source_dir).resolve()
    target = Path(target_dir).resolve()
    managed = source_files(source)
    package = _read_json(source / "package.json", label="package.json")
    lock = _read_json(source / "package-lock.json", label="package-lock.json")
    dependencies = _validated_dependencies(package, lock)
    minimum_node = _minimum_node_version(package)
    hashes = {relative: _file_sha256(source / relative) for relative in managed}
    manifest = {
        "schema_version": SEED_SCHEMA_VERSION,
        "runtime": RUNTIME_NAME,
        "worker_version": str(package.get("version") or ""),
        "entrypoint": "src/worker.ts",
        "minimum_node_version": minimum_node,
        "bundle_hash": _bundle_hash(hashes),
        "files": dict(sorted(hashes.items())),
        "dependencies": dict(sorted(dependencies.items())),
    }

    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent))
    try:
        for relative in managed:
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, destination)
        (staging / MANIFEST_NAME).write_text(_json_document(manifest), encoding="utf-8")
        validate_runtime_seed(staging)
        if target.exists():
            shutil.rmtree(target)
        staging.replace(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest


def load_runtime_manifest(seed_dir: str | Path) -> dict[str, Any]:
    return _read_json(Path(seed_dir) / MANIFEST_NAME, label=MANIFEST_NAME)


def validate_runtime_seed(seed_dir: str | Path) -> dict[str, Any]:
    root = Path(seed_dir)
    manifest = load_runtime_manifest(root)
    if manifest.get("schema_version") != SEED_SCHEMA_VERSION or manifest.get("runtime") != RUNTIME_NAME:
        raise RuntimeSeedError("Pi Worker runtime manifest schema is unsupported")
    if manifest.get("entrypoint") != "src/worker.ts":
        raise RuntimeSeedError("Pi Worker runtime manifest entrypoint is invalid")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise RuntimeSeedError("Pi Worker runtime manifest files are missing")
    expected_files = set(source_files(root))
    if set(files) != expected_files:
        raise RuntimeSeedError("Pi Worker runtime manifest file inventory is incomplete")
    hashes: dict[str, str] = {}
    for relative, expected_hash in files.items():
        if not isinstance(relative, str) or not _safe_relative_path(relative):
            raise RuntimeSeedError("Pi Worker runtime manifest contains an unsafe path")
        if not isinstance(expected_hash, str) or not _SHA256.fullmatch(expected_hash):
            raise RuntimeSeedError(f"Pi Worker runtime manifest hash is invalid: {relative}")
        actual_hash = _file_sha256(root / relative)
        if actual_hash != expected_hash:
            raise RuntimeSeedError(f"Pi Worker runtime seed hash mismatch: {relative}")
        hashes[relative] = actual_hash
    bundle_hash = manifest.get("bundle_hash")
    if not isinstance(bundle_hash, str) or bundle_hash != _bundle_hash(hashes):
        raise RuntimeSeedError("Pi Worker runtime bundle hash mismatch")
    package = _read_json(root / "package.json", label="package.json")
    lock = _read_json(root / "package-lock.json", label="package-lock.json")
    dependencies = _validated_dependencies(package, lock)
    if manifest.get("dependencies") != dict(sorted(dependencies.items())):
        raise RuntimeSeedError("Pi Worker runtime dependency inventory is inconsistent")
    if manifest.get("minimum_node_version") != _minimum_node_version(package):
        raise RuntimeSeedError("Pi Worker runtime Node requirement is inconsistent")
    return manifest


def _validated_dependencies(package: Mapping[str, Any], lock: Mapping[str, Any]) -> dict[str, str]:
    dependencies = package.get("dependencies")
    locked = lock.get("packages", {}).get("", {}).get("dependencies") if isinstance(lock.get("packages"), dict) else None
    if not isinstance(dependencies, dict) or not all(
        isinstance(name, str) and isinstance(version, str) for name, version in dependencies.items()
    ):
        raise RuntimeSeedError("Pi Worker package dependencies are invalid")
    if locked != dependencies:
        raise RuntimeSeedError("Pi Worker package-lock root dependencies do not match package.json")
    return dict(dependencies)


def _minimum_node_version(package: Mapping[str, Any]) -> str:
    engines = package.get("engines")
    raw = engines.get("node") if isinstance(engines, dict) else None
    match = re.fullmatch(r">=(\d+\.\d+\.\d+)", str(raw or ""))
    if match is None:
        raise RuntimeSeedError("Pi Worker Node engine must use an exact >=x.y.z minimum")
    return match.group(1)


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeSeedError(f"Cannot read Pi Worker {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeSeedError(f"Pi Worker {label} must contain a JSON object")
    return value


def _file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise RuntimeSeedError(f"Cannot read Pi Worker seed file {path}: {exc}") from exc


def _bundle_hash(hashes: Mapping[str, str]) -> str:
    digest = hashlib.sha256()
    for relative, file_hash in sorted(hashes.items()):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _safe_relative_path(value: str) -> bool:
    path = Path(value)
    return not path.is_absolute() and value == path.as_posix() and ".." not in path.parts


def _json_document(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
