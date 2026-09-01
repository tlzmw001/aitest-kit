from __future__ import annotations

import json
from pathlib import Path

import pytest

from aitest_kit.agent.seed import RuntimeSeedError, build_runtime_seed, validate_runtime_seed


def _source(root: Path) -> Path:
    source = root / "source"
    (source / "src").mkdir(parents=True)
    (source / "package.json").write_text(
        json.dumps(
            {
                "name": "@aitest/pi-worker",
                "version": "0.1.0",
                "engines": {"node": ">=22.19.0"},
                "dependencies": {"pi": "1.2.3"},
            }
        ),
        encoding="utf-8",
    )
    (source / "package-lock.json").write_text(
        json.dumps({"packages": {"": {"dependencies": {"pi": "1.2.3"}}}}),
        encoding="utf-8",
    )
    (source / "src" / "worker.ts").write_text("console.log('worker')\n", encoding="utf-8")
    return source


def test_seed_build_is_deterministic_and_excludes_unmanaged_files(tmp_path: Path) -> None:
    source = _source(tmp_path)
    (source / "test").mkdir()
    (source / "test" / "worker.test.ts").write_text("not shipped\n", encoding="utf-8")
    target = tmp_path / "seed"

    first = build_runtime_seed(source, target)
    second = build_runtime_seed(source, target)

    assert first == second
    assert validate_runtime_seed(target)["bundle_hash"] == first["bundle_hash"]
    assert not (target / "test").exists()


def test_seed_source_change_updates_bundle_hash(tmp_path: Path) -> None:
    source = _source(tmp_path)
    target = tmp_path / "seed"
    first = build_runtime_seed(source, target)

    (source / "src" / "worker.ts").write_text("console.log('changed')\n", encoding="utf-8")
    second = build_runtime_seed(source, target)

    assert second["bundle_hash"] != first["bundle_hash"]


def test_seed_validation_rejects_modified_content(tmp_path: Path) -> None:
    source = _source(tmp_path)
    target = tmp_path / "seed"
    build_runtime_seed(source, target)
    (target / "src" / "worker.ts").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(RuntimeSeedError, match="hash mismatch"):
        validate_runtime_seed(target)


def test_seed_validation_rejects_package_lock_drift(tmp_path: Path) -> None:
    source = _source(tmp_path)
    lock = json.loads((source / "package-lock.json").read_text(encoding="utf-8"))
    lock["packages"][""]["dependencies"]["pi"] = "9.9.9"
    (source / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")

    with pytest.raises(RuntimeSeedError, match="do not match"):
        build_runtime_seed(source, tmp_path / "seed")
