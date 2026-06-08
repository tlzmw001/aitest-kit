"""Scene routing fixture client for coupon_system generated tests."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import httpx
import pytest

from aitest_kit.runtime_variables import require_envs
from test_workspace.targets.coupon_system.helpers import grpc_ops
from test_workspace.targets.coupon_system.helpers.redis_ops import RedisTracker


DEFAULT_ITEM: dict[str, Any] = {
    "item_id": "COUPON_ROUTE_001",
    "coupon_type": "discount",
    "value": 80,
    "min_spend": 5000,
    "expire_days": 7,
}

FALLBACK_SCORE_KEYS = ("coupon:fallback:score:3001", "coupon:fallback:score:default")


class SceneRoutingClient:
    def __init__(self, http_base_url: str, grpc_target: str, redis_url: str) -> None:
        self.http_base_url = http_base_url.rstrip("/")
        self.grpc_target = grpc_target
        self._http = httpx.Client(transport=httpx.HTTPTransport(), timeout=10.0)
        self._redis = RedisTracker(url=redis_url)

    def close(self) -> None:
        self.clear_fallback_scores()
        self._redis.close()
        self._http.close()

    def prepare_stock(self, *, coupon_id: str = "COUPON_ROUTE_001", stock: int = 100) -> None:
        self._post_main(
            "/api/v1/admin/stock",
            {"coupon_id": coupon_id, "stock": stock, "ttl": 86400},
        )

    def set_fallback_scores(self, scores: dict[str, Any] | None = None) -> None:
        self.clear_fallback_scores()
        for key, value in (scores or {}).items():
            self._redis.set(str(key), str(value), ex=86400)

    def clear_fallback_scores(self) -> None:
        self._redis.delete(*FALLBACK_SCORE_KEYS)

    def recommend_http(self, *, request_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        body = self._request_body(request_overrides)
        resp = self._http.post(f"{self.http_base_url}/api/v1/recommend", json=body)
        resp.raise_for_status()
        return resp.json()

    def recommend_grpc(self, *, request_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        return grpc_ops.recommend(self.grpc_target, self._request_body(request_overrides))

    def _request_body(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        body = {
            "user_id": "u_route_default",
            "scene_name": "game",
            "device": "mobile",
            "policy_id": "",
            "external": 0,
            "reqId": "req_route_default",
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


@pytest.fixture
def setup_scene_routing() -> SceneRoutingClient:
    env = require_envs(["COUPON_SYSTEM_BASE_URL", "COUPON_GRPC_TARGET", "REDIS_URL"])
    client = SceneRoutingClient(
        http_base_url=env["COUPON_SYSTEM_BASE_URL"],
        grpc_target=env["COUPON_GRPC_TARGET"],
        redis_url=env["REDIS_URL"],
    )
    try:
        yield client
    finally:
        client.close()
