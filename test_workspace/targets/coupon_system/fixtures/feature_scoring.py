"""Feature scoring fixture client for coupon_system generated tests."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import httpx
import pytest

from aitest_kit.runtime_variables import require_envs
from test_workspace.targets.coupon_system.helpers import grpc_ops


AB_OFF = {"coarse_rank_exp_game": "cr_off", "calibration_exp_game": "cal_off"}

DEFAULT_FEATURES: dict[str, Any] = {
    "gender": "male",
    "age": 28,
    "total_spend": 30000,
    "purchase_frequency": 4,
    "register_days": 120,
    "is_new_user": True,
    "is_member": True,
}

DEFAULT_ITEM: dict[str, Any] = {
    "item_id": "COUPON_FEAT_001",
    "coupon_type": "discount",
    "value": 80,
    "min_spend": 5000,
    "expire_days": 7,
}


class FeatureScoringClient:
    def __init__(self, http_base_url: str, ab_base_url: str, grpc_target: str) -> None:
        self.http_base_url = http_base_url.rstrip("/")
        self.ab_base_url = ab_base_url.rstrip("/")
        self.grpc_target = grpc_target
        self._http = httpx.Client(transport=httpx.HTTPTransport(), timeout=10.0)
        self._whitelist_users: set[str] = set()

    def close(self) -> None:
        for user_id in sorted(self._whitelist_users):
            self._delete_ab(f"/api/v1/ab/whitelist/{user_id}")
        self._http.close()

    def prepare_user(
        self,
        *,
        user_id: str,
        features: dict[str, Any] | None = None,
        disable_ab: bool = True,
    ) -> None:
        if disable_ab:
            self._put_ab(f"/api/v1/ab/whitelist/{user_id}", {"strategy_map": AB_OFF})
            self._whitelist_users.add(user_id)
        if features is not None:
            self._post_main(
                "/api/v1/admin/user-features",
                {"user_id": user_id, "features": features},
            )

    def prepare_stock(self, *, coupon_id: str, stock: int = 100) -> None:
        self._post_main(
            "/api/v1/admin/stock",
            {"coupon_id": coupon_id, "stock": stock, "ttl": 86400},
        )

    def recommend_http(self, *, request_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        body = self._request_body(request_overrides)
        resp = self._http.post(f"{self.http_base_url}/api/v1/recommend", json=body)
        resp.raise_for_status()
        return resp.json()

    def recommend_grpc(self, *, request_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        return grpc_ops.recommend(self.grpc_target, self._request_body(request_overrides))

    def _request_body(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        body = {
            "user_id": "u_feature_default",
            "scene_name": "game",
            "device": "mobile",
            "policy_id": "",
            "external": 0,
            "reqId": "req_feature_default",
            "score_threshold": 0.0,
            "max_claim_per_request": 1,
            "context": {"channel": "test"},
            "items": [deepcopy(DEFAULT_ITEM)],
        }
        body.update(overrides or {})
        return body

    def _post_main(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._http.post(f"{self.http_base_url}{path}", json=payload)
        resp.raise_for_status()
        return resp.json()

    def _put_ab(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._http.put(f"{self.ab_base_url}{path}", json=payload)
        resp.raise_for_status()
        return resp.json()

    def _delete_ab(self, path: str) -> None:
        resp = self._http.delete(f"{self.ab_base_url}{path}")
        if resp.status_code not in {200, 204, 404}:
            resp.raise_for_status()


@pytest.fixture
def setup_feature_scoring() -> FeatureScoringClient:
    env = require_envs(["COUPON_SYSTEM_BASE_URL", "COUPON_AB_BASE_URL", "COUPON_GRPC_TARGET"])
    client = FeatureScoringClient(
        http_base_url=env["COUPON_SYSTEM_BASE_URL"],
        ab_base_url=env["COUPON_AB_BASE_URL"],
        grpc_target=env["COUPON_GRPC_TARGET"],
    )
    try:
        yield client
    finally:
        client.close()
