"""Scene routing module Harness for coupon_system tests."""
from __future__ import annotations

from copy import deepcopy
from functools import cached_property
from typing import Any

import httpx

from aitest_kit.runtime_variables import require_env
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


class SceneRoutingHarness:
    def __init__(self) -> None:
        self._http = httpx.Client(transport=httpx.HTTPTransport(), timeout=10.0)
        self._redis: RedisTracker | None = None

    @cached_property
    def http_base_url(self) -> str:
        return require_env("COUPON_SYSTEM_BASE_URL").rstrip("/")

    @cached_property
    def grpc_target(self) -> str:
        return require_env("COUPON_GRPC_TARGET")

    @property
    def redis_tracker(self) -> RedisTracker:
        if self._redis is None:
            self._redis = RedisTracker(url=require_env("REDIS_URL"))
        return self._redis

    def close(self) -> None:
        if self._redis is not None:
            self._redis.delete(*FALLBACK_SCORE_KEYS)
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
            self.redis_tracker.set(str(key), str(value), ex=86400)

    def clear_fallback_scores(self) -> None:
        self.redis_tracker.delete(*FALLBACK_SCORE_KEYS)

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
