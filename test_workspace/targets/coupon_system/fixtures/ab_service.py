"""AB service module fixtures."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import httpx
import pytest
from fastapi.testclient import TestClient

from ab_experiment_sdk.remote_client import RemoteABExperimentSDK
from ab_experiment_sdk.service import create_app

logger = logging.getLogger(__name__)

_client = httpx.Client(transport=httpx.HTTPTransport())


def _experiment_payload(
    name: str,
    strategies: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    if strategies is None:
        strategies = [
            {"id": "s_a", "hash_range": [0, 50], "params": {"bucket": "a"}},
            {"id": "s_b", "hash_range": [50, 100], "params": {"bucket": "b"}},
        ]
    return {
        "name": name,
        "strategies": strategies,
    }


def _standard_experiments() -> dict[str, dict[str, Any]]:
    return {
        "exp_ab_basic": _experiment_payload("exp_ab_basic"),
        "exp_ab_extra": _experiment_payload(
            "exp_ab_extra",
            [{"id": "extra_on", "hash_range": [0, 100], "params": {"extra": True}}],
        ),
        "exp_game": _experiment_payload(
            "exp_game",
            [{"id": "game_on", "hash_range": [0, 100], "params": {"k": 1}}],
        ),
        "exp_cal": _experiment_payload(
            "exp_cal",
            [{"id": "cal_on", "hash_range": [0, 100], "params": {"b": 2}}],
        ),
    }


def write_experiments_file(path: Path, experiments: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"experiments": experiments}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_isolated_client(
    tmp_path: Path,
    experiments: Optional[list[dict[str, Any]]] = None,
    whitelist: Optional[dict[str, dict[str, str]]] = None,
    whitelist_text: Optional[str] = None,
) -> tuple:
    experiments_path = tmp_path / "experiments.json"
    whitelist_path = tmp_path / "whitelist.json"
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


class ABServiceCase:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._experiment_snapshots: dict[str, Optional[dict[str, Any]]] = {}
        self._whitelist_snapshot: Optional[dict[str, Any]] = None

    def request(self, method: str, path: str, json_body: Optional[dict] = None) -> httpx.Response:
        return _client.request(method, f"{self.base_url}{path}", json=json_body, timeout=10.0)

    def get(self, path: str) -> httpx.Response:
        return self.request("GET", path)

    def post(self, path: str, json_body: Optional[dict] = None) -> httpx.Response:
        return self.request("POST", path, json_body)

    def put(self, path: str, json_body: Optional[dict] = None) -> httpx.Response:
        return self.request("PUT", path, json_body)

    def delete(self, path: str) -> httpx.Response:
        return self.request("DELETE", path)

    def snapshot_whitelist(self) -> None:
        if self._whitelist_snapshot is not None:
            return
        response = self.get("/api/v1/ab/whitelist")
        response.raise_for_status()
        body = response.json()
        self._whitelist_snapshot = body if isinstance(body, dict) else {}

    def snapshot_experiment(self, name: str) -> None:
        if name in self._experiment_snapshots:
            return
        response = self.get(f"/api/v1/ab/experiments/{name}")
        if response.status_code == 200:
            self._experiment_snapshots[name] = response.json()
            return
        if response.status_code == 404:
            self._experiment_snapshots[name] = None
            return
        response.raise_for_status()

    def upsert_experiment(self, payload: dict[str, Any]) -> None:
        name = payload["name"]
        self.snapshot_experiment(name)
        response = self.post("/api/v1/ab/experiments", payload)
        if response.status_code == 409:
            response = self.put(f"/api/v1/ab/experiments/{name}", payload)
        response.raise_for_status()

    def set_user_whitelist(self, user_id: str, strategy_map: dict[str, str]) -> None:
        self.snapshot_whitelist()
        response = self.put(
            f"/api/v1/ab/whitelist/{user_id}",
            {"strategy_map": strategy_map},
        )
        response.raise_for_status()

    def replace_whitelist(self, whitelist: dict[str, dict[str, str]]) -> None:
        self.snapshot_whitelist()
        response = self.put("/api/v1/ab/whitelist", whitelist)
        response.raise_for_status()

    def restore(self) -> None:
        if self._whitelist_snapshot is not None:
            response = self.put("/api/v1/ab/whitelist", self._whitelist_snapshot)
            if response.status_code >= 400:
                logger.warning("restore AB whitelist failed: %s %s", response.status_code, response.text)

        for name, payload in reversed(list(self._experiment_snapshots.items())):
            if payload is None:
                response = self.delete(f"/api/v1/ab/experiments/{name}")
                if response.status_code not in {200, 404}:
                    logger.warning("delete AB experiment failed: %s %s", name, response.text)
                continue
            response = self.put(f"/api/v1/ab/experiments/{name}", payload)
            if response.status_code == 404:
                response = self.post("/api/v1/ab/experiments", payload)
            if response.status_code >= 400:
                logger.warning("restore AB experiment failed: %s %s", name, response.text)

    def remote_sdk(self, tmp_path: Path) -> tuple:
        client, _, _ = build_isolated_client(
            tmp_path,
            experiments=list(_standard_experiments().values()),
            whitelist={"u1": {"exp_game": "game_on"}},
        )
        return RemoteABExperimentSDK(base_url="http://testserver", client=client), client


@pytest.fixture
def setup_ab_service(ab_base_url):
    """Prepare AB service state through its public API and restore it after each case."""
    case = ABServiceCase(ab_base_url)

    def _setup(case_id: str) -> ABServiceCase:
        standard = _standard_experiments()
        for name in _experiments_for_case(case_id):
            case.upsert_experiment(standard[name])

        if case_id == "TC-ABS-003":
            case.set_user_whitelist("u_abs_white", {"exp_ab_basic": "s_b"})
        elif case_id == "TC-ABS-013":
            case.set_user_whitelist("u_white", {"exp_game": "game_on"})
        elif case_id == "TC-ABS-016":
            case.set_user_whitelist("user_b", {"exp_game": "game_on"})
        elif case_id == "TC-ABS-017":
            case.replace_whitelist({"user_b": {"exp_game": "game_on"}})
        elif case_id == "TC-ABS-023":
            case.upsert_experiment(_experiment_payload(
                "exp_abs_overlap",
                [
                    {"id": "s_first", "hash_range": [0, 80], "params": {}},
                    {"id": "s_second", "hash_range": [50, 100], "params": {}},
                ],
            ))
        elif case_id == "TC-ABS-024":
            case.upsert_experiment(_experiment_payload("exp_abs_empty", []))
        return case

    yield _setup
    case.restore()


def _experiments_for_case(case_id: str) -> set[str]:
    mapping = {
        "TC-ABS-002": {"exp_ab_basic"},
        "TC-ABS-003": {"exp_ab_basic"},
        "TC-ABS-004": {"exp_ab_basic", "exp_ab_extra"},
        "TC-ABS-006": {"exp_ab_basic"},
        "TC-ABS-007": {"exp_game", "exp_cal"},
        "TC-ABS-008": {"exp_game"},
        "TC-ABS-013": {"exp_game"},
        "TC-ABS-035": {"exp_game", "exp_cal"},
        "TC-ABS-036": {"exp_game", "exp_cal"},
        "TC-ABS-037": {"exp_game", "exp_cal"},
        "TC-ABS-038": {"exp_game", "exp_cal"},
        "TC-ABS-039": {"exp_game", "exp_cal"},
    }
    return set(mapping.get(case_id, set()))
