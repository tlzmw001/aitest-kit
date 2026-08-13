"""Reusable experiment and isolated-app resources for AB service tests."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from ab_experiment_sdk.service import create_app


def experiment_payload(
    name: str,
    strategies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if strategies is None:
        strategies = [
            {"id": "s_a", "hash_range": [0, 50], "params": {"bucket": "a"}},
            {"id": "s_b", "hash_range": [50, 100], "params": {"bucket": "b"}},
        ]
    return {"name": name, "strategies": strategies}


def standard_experiments() -> dict[str, dict[str, Any]]:
    return {
        "exp_ab_basic": experiment_payload("exp_ab_basic"),
        "exp_ab_extra": experiment_payload(
            "exp_ab_extra",
            [{"id": "extra_on", "hash_range": [0, 100], "params": {"extra": True}}],
        ),
        "exp_game": experiment_payload(
            "exp_game",
            [{"id": "game_on", "hash_range": [0, 100], "params": {"k": 1}}],
        ),
        "exp_cal": experiment_payload(
            "exp_cal",
            [{"id": "cal_on", "hash_range": [0, 100], "params": {"b": 2}}],
        ),
    }


def build_isolated_client(
    root: Path,
    *,
    experiments: list[dict[str, Any]] | None = None,
    whitelist: dict[str, dict[str, str]] | None = None,
    whitelist_text: str | None = None,
) -> tuple[TestClient, Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    experiments_path = root / "experiments.json"
    whitelist_path = root / "whitelist.json"
    if experiments is not None:
        write_experiments_file(experiments_path, experiments)
    if whitelist_text is not None:
        whitelist_path.write_text(whitelist_text, encoding="utf-8")
    app = create_app(
        experiments_path=str(experiments_path),
        whitelist_path=str(whitelist_path),
        initial_whitelist=whitelist,
    )
    return TestClient(app), experiments_path, whitelist_path


def write_experiments_file(path: Path, experiments: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"experiments": experiments}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("cannot locate repository root")
