"""AB experiment module Harness for coupon_system tests."""
from __future__ import annotations

from copy import deepcopy
from functools import cached_property
from typing import Any

import httpx

from aitest_kit.runtime_variables import require_env
from test_workspace.targets.coupon_system.helpers import grpc_ops


DEFAULT_ITEM: dict[str, Any] = {
    "item_id": "COUPON_AB_001",
    "coupon_type": "discount",
    "value": 80,
    "min_spend": 5000,
    "expire_days": 7,
}


class AbExperimentHarness:
    def __init__(self) -> None:
        self._http = httpx.Client(transport=httpx.HTTPTransport(), timeout=10.0)
        self._whitelist_users: set[str] = set()

    @cached_property
    def http_base_url(self) -> str:
        return require_env("COUPON_SYSTEM_BASE_URL").rstrip("/")

    @cached_property
    def ab_base_url(self) -> str:
        return require_env("COUPON_AB_BASE_URL").rstrip("/")

    @cached_property
    def grpc_target(self) -> str:
        return require_env("COUPON_GRPC_TARGET")

    def close(self) -> None:
        for user_id in sorted(self._whitelist_users):
            self._delete_ab(f"/api/v1/ab/whitelist/{user_id}")
        self._http.close()

    def prepare_stock(self, *, coupon_id: str = "COUPON_AB_001", stock: int = 100) -> None:
        self._post_main(
            "/api/v1/admin/stock",
            {"coupon_id": coupon_id, "stock": stock, "ttl": 86400},
        )

    def set_whitelist(self, *, user_id: str, strategy_map: dict[str, str]) -> None:
        self._put_ab(
            f"/api/v1/ab/whitelist/{user_id}",
            {"strategy_map": strategy_map},
        )
        self._whitelist_users.add(user_id)

    def recommend_http(self, *, request_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        body = self._request_body(request_overrides)
        resp = self._http.post(f"{self.http_base_url}/api/v1/recommend", json=body)
        resp.raise_for_status()
        return resp.json()

    def recommend_grpc(self, *, request_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        return grpc_ops.recommend(self.grpc_target, self._request_body(request_overrides))

    def experiment_keys(self, response: dict[str, Any]) -> set[str]:
        return set(response.get("experiment_info", {}).keys())

    def _request_body(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        body = {
            "user_id": "u_ab_default",
            "scene_name": "game",
            "device": "mobile",
            "policy_id": "",
            "external": 0,
            "reqId": "req_ab_default",
            "score_threshold": 0.0,
            "max_claim_per_request": 1,
            "context": {},
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
