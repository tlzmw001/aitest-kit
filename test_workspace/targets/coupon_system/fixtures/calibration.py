"""Calibration fixture client for coupon_system generated tests."""
from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx
import pytest

from aitest_kit.runtime_variables import require_envs
from test_workspace.targets.coupon_system.helpers import grpc_ops


DEFAULT_ITEM: dict[str, Any] = {
    "item_id": "COUPON_CAL_001",
    "coupon_type": "discount",
    "value": 80,
    "min_spend": 5000,
    "expire_days": 7,
}


PIECEWISE_SEGMENTS: list[dict[str, Any]] = [
    {"range": [0.0, 0.3], "k": 0.5, "b": 0.1},
    {"range": [0.3, 0.7], "k": 1.0, "b": 0.0},
    {"range": [0.7, 1.0], "k": 1.5, "b": -0.2},
]


class CalibrationClient:
    def __init__(self, http_base_url: str, ab_base_url: str, grpc_target: str) -> None:
        self.http_base_url = http_base_url.rstrip("/")
        self.ab_base_url = ab_base_url.rstrip("/")
        self.grpc_target = grpc_target
        self._http = httpx.Client(transport=httpx.HTTPTransport(), timeout=10.0)
        self._temp_dir = tempfile.TemporaryDirectory(prefix="aitest_calibration_")
        self._original_experiments: dict[str, dict[str, Any]] = {}
        self._whitelist_users: set[str] = set()

    def close(self) -> None:
        for name, experiment in reversed(list(self._original_experiments.items())):
            self._put_ab(f"/api/v1/ab/experiments/{name}", experiment)
        for user_id in sorted(self._whitelist_users):
            self._delete_ab(f"/api/v1/ab/whitelist/{user_id}")
        self._http.close()
        self._temp_dir.cleanup()

    def run_http_calibration(
        self,
        *,
        case_id: str,
        linear_files: dict[Any, list[dict[str, Any]]] | None = None,
        piecewise_files: dict[Any, list[dict[str, Any]]] | None = None,
        enable_calibration: bool = True,
        request_overrides: dict[str, Any] | None = None,
        user_features: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = self._request_body(case_id=case_id, overrides=request_overrides)
        self._prepare_runtime(
            case_id=case_id,
            user_id=str(body["user_id"]),
            linear_files=linear_files,
            piecewise_files=piecewise_files,
            enable_calibration=enable_calibration,
            user_features=user_features,
            item_id=str(body["items"][0]["item_id"]),
        )
        resp = self._http.post(f"{self.http_base_url}/api/v1/recommend", json=body)
        resp.raise_for_status()
        return resp.json()

    def run_grpc_calibration(
        self,
        *,
        case_id: str,
        linear_files: dict[Any, list[dict[str, Any]]] | None = None,
        piecewise_files: dict[Any, list[dict[str, Any]]] | None = None,
        enable_calibration: bool = True,
        request_overrides: dict[str, Any] | None = None,
        user_features: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = self._request_body(case_id=case_id, overrides=request_overrides)
        self._prepare_runtime(
            case_id=case_id,
            user_id=str(body["user_id"]),
            linear_files=linear_files,
            piecewise_files=piecewise_files,
            enable_calibration=enable_calibration,
            user_features=user_features,
            item_id=str(body["items"][0]["item_id"]),
        )
        return grpc_ops.recommend(self.grpc_target, body)

    def matches_linear(self, response: dict[str, Any], *, k: float, b: float = 0.0) -> bool:
        score = self.raw_score(response)
        return self._same_score(self.calibrated_score(response), self.expected_linear(score, k=k, b=b))

    def matches_piecewise(
        self,
        response: dict[str, Any],
        *,
        segments: list[dict[str, Any]] | None = None,
    ) -> bool:
        score = self.raw_score(response)
        return self._same_score(
            self.calibrated_score(response),
            self.expected_piecewise(score, segments or PIECEWISE_SEGMENTS),
        )

    def matches_piecewise_then_linear(
        self,
        response: dict[str, Any],
        *,
        linear_k: float,
        linear_b: float = 0.0,
        segments: list[dict[str, Any]] | None = None,
    ) -> bool:
        score = self.raw_score(response)
        mid = self.expected_piecewise(score, segments or PIECEWISE_SEGMENTS)
        expected = self.expected_linear(mid, k=linear_k, b=linear_b)
        return self._same_score(self.calibrated_score(response), expected)

    def matches_unchanged(self, response: dict[str, Any]) -> bool:
        return self._same_score(self.calibrated_score(response), self.raw_score(response))

    def raw_score(self, response: dict[str, Any]) -> float:
        return float(response["results"][0]["score"])

    def calibrated_score(self, response: dict[str, Any]) -> float:
        return float(response["results"][0]["calibrated_score"])

    def expected_linear(self, score: float, *, k: float, b: float = 0.0) -> float:
        return self._round_score(self._clamp(k * score + b))

    def expected_piecewise(self, score: float, segments: list[dict[str, Any]]) -> float:
        for index, segment in enumerate(segments):
            low, high = segment["range"]
            upper_match = score <= high if index == len(segments) - 1 else score < high
            if score >= low and upper_match:
                return self._round_score(self._clamp(segment["k"] * score + segment.get("b", 0.0)))
        return self._round_score(score)

    def _prepare_runtime(
        self,
        *,
        case_id: str,
        user_id: str,
        linear_files: dict[Any, list[dict[str, Any]]] | None,
        piecewise_files: dict[Any, list[dict[str, Any]]] | None,
        enable_calibration: bool,
        user_features: dict[str, Any] | None,
        item_id: str,
    ) -> None:
        dirs = self._write_calibration_files(
            case_id=case_id,
            linear_files=linear_files or {},
            piecewise_files=piecewise_files or {},
        )
        strategy_id = self._strategy_id(case_id)
        self._replace_experiment(
            "calibration_exp_game",
            strategy_id,
            {
                "enable_calibration": enable_calibration,
                "calibration_dir": {
                    "linear": str(dirs["linear"]),
                    "piecewise": str(dirs["piecewise"]),
                },
            },
        )
        self._force_whitelist(user_id, {
            "coarse_rank_exp_game": "cr_off",
            "calibration_exp_game": strategy_id,
        })
        self._init_stock(item_id, 100)
        if user_features:
            self._set_user_features(user_id, user_features)

    def _write_calibration_files(
        self,
        *,
        case_id: str,
        linear_files: dict[Any, list[dict[str, Any]]],
        piecewise_files: dict[Any, list[dict[str, Any]]],
    ) -> dict[str, Path]:
        case_root = Path(self._temp_dir.name) / self._safe_name(case_id)
        linear_dir = case_root / "linear"
        piecewise_dir = case_root / "piecewise"
        linear_dir.mkdir(parents=True, exist_ok=True)
        piecewise_dir.mkdir(parents=True, exist_ok=True)
        self._write_versioned_rules(linear_dir, linear_files)
        self._write_versioned_rules(piecewise_dir, piecewise_files)
        return {"linear": linear_dir, "piecewise": piecewise_dir}

    def _write_versioned_rules(self, directory: Path, files: dict[Any, list[dict[str, Any]]]) -> None:
        for version, rules in files.items():
            path = directory / f"{version}.json"
            path.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")

    def _replace_experiment(self, name: str, strategy_id: str, params: dict[str, Any]) -> None:
        self._snapshot_experiment(name)
        self._put_ab(
            f"/api/v1/ab/experiments/{name}",
            {
                "name": name,
                "strategies": [
                    {
                        "id": strategy_id,
                        "hash_range": [0, 100],
                        "params": params,
                    }
                ],
            },
        )

    def _snapshot_experiment(self, name: str) -> None:
        if name in self._original_experiments:
            return
        self._original_experiments[name] = self._get_ab(f"/api/v1/ab/experiments/{name}")

    def _force_whitelist(self, user_id: str, strategy_map: dict[str, str]) -> None:
        self._put_ab(f"/api/v1/ab/whitelist/{user_id}", {"strategy_map": strategy_map})
        self._whitelist_users.add(user_id)

    def _init_stock(self, coupon_id: str, stock: int) -> None:
        resp = self._http.post(
            f"{self.http_base_url}/api/v1/admin/stock",
            json={"coupon_id": coupon_id, "stock": stock, "ttl": 86400},
        )
        resp.raise_for_status()

    def _set_user_features(self, user_id: str, features: dict[str, Any]) -> None:
        resp = self._http.post(
            f"{self.http_base_url}/api/v1/admin/user-features",
            json={"user_id": user_id, "features": features},
        )
        resp.raise_for_status()

    def _request_body(self, *, case_id: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        safe = self._safe_name(case_id).lower()
        body = {
            "user_id": f"u_{safe}",
            "scene_name": "game",
            "device": "mobile",
            "policy_id": "",
            "external": 0,
            "reqId": f"req_{safe}",
            "score_threshold": 0.0,
            "max_claim_per_request": 1,
            "context": {},
            "items": [deepcopy(DEFAULT_ITEM)],
        }
        body.update(overrides or {})
        return body

    def _get_ab(self, path: str) -> dict[str, Any]:
        resp = self._http.get(f"{self.ab_base_url}{path}")
        resp.raise_for_status()
        return resp.json()

    def _put_ab(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._http.put(f"{self.ab_base_url}{path}", json=payload)
        resp.raise_for_status()
        return resp.json()

    def _delete_ab(self, path: str) -> None:
        resp = self._http.delete(f"{self.ab_base_url}{path}")
        resp.raise_for_status()

    def _strategy_id(self, case_id: str) -> str:
        return f"aitest_{self._safe_name(case_id).lower()}"

    def _safe_name(self, value: str) -> str:
        return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")

    def _same_score(self, actual: float, expected: float) -> bool:
        return abs(float(actual) - float(expected)) <= 0.0001 + 1e-9

    def _round_score(self, value: float) -> float:
        return round(float(value), 4)

    def _clamp(self, value: float) -> float:
        return max(0.0, min(1.0, float(value)))


@pytest.fixture
def setup_calibration() -> CalibrationClient:
    env = require_envs([
        "COUPON_SYSTEM_BASE_URL",
        "COUPON_AB_BASE_URL",
        "COUPON_GRPC_TARGET",
    ])
    client = CalibrationClient(
        http_base_url=env["COUPON_SYSTEM_BASE_URL"],
        ab_base_url=env["COUPON_AB_BASE_URL"],
        grpc_target=env["COUPON_GRPC_TARGET"],
    )
    try:
        yield client
    finally:
        client.close()
