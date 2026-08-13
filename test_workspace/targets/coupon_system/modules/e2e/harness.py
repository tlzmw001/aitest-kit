"""Reusable actions for coupon_system end-to-end tests."""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from functools import cached_property

from aitest_kit.runtime_variables import require_env
from test_workspace.targets.coupon_system.helpers import grpc_ops
from test_workspace.targets.coupon_system.helpers import http as http_helper
from test_workspace.targets.coupon_system.helpers.redis_ops import RedisTracker


logger = logging.getLogger(__name__)

_E2E_WHITELIST = {
    "coarse_rank_exp_game": "cr_v2_full",
    "calibration_exp_game": "cal_on",
}

_DISCOUNT_ITEM = {
    "item_id": "COUPON_ACT_001",
    "coupon_type": "discount",
    "value": 80,
    "min_spend": 5000,
    "expire_days": 7,
}

_FREE_SHIPPING_ITEM = {
    "item_id": "COUPON_SHIP_001",
    "coupon_type": "free_shipping",
    "value": 1,
    "min_spend": 0,
    "expire_days": 7,
}


@dataclass
class E2eHarness:
    """Actions and owned cleanup state for one E2E test."""

    users: set[str] = field(default_factory=set)
    whitelist_users: set[str] = field(default_factory=set)
    _redis_tracker: RedisTracker | None = field(default=None, init=False)

    @cached_property
    def http_base_url(self) -> str:
        return require_env("HTTP_BASE_URL").rstrip("/")

    @cached_property
    def grpc_target(self) -> str:
        return require_env("GRPC_TARGET")

    @cached_property
    def ab_base_url(self) -> str:
        return require_env("AB_SERVICE_URL").rstrip("/")

    @property
    def redis_tracker(self) -> RedisTracker:
        if self._redis_tracker is None:
            self._redis_tracker = RedisTracker(url=require_env("REDIS_URL"))
        return self._redis_tracker

    def set_experiment_whitelist(self, user_id: str) -> None:
        """Select the deterministic E2E experiment branches for one user."""
        self.cleanup_user(user_id)
        http_helper.put(
            self.ab_base_url,
            f"/api/v1/ab/whitelist/{user_id}",
            json={"strategy_map": _E2E_WHITELIST},
        )
        self.users.add(user_id)
        self.whitelist_users.add(user_id)

    def cleanup_user(self, user_id: str) -> None:
        instance_set_key = f"coupon:user:{user_id}:instances"
        instance_ids = self.redis_tracker.smembers(instance_set_key)
        instance_keys = [f"coupon:instance:{instance_id}" for instance_id in instance_ids]
        self.redis_tracker.delete(
            *instance_keys,
            instance_set_key,
            f"coupon:user:{user_id}:claimed",
        )

    def set_stock(self, coupon_id: str, stock: int) -> None:
        http_helper.post(
            self.http_base_url,
            "/api/v1/admin/stock",
            json={"coupon_id": coupon_id, "stock": stock, "ttl": 86400},
        )

    def stock(self, coupon_id: str) -> int:
        return http_helper.get(
            self.http_base_url,
            f"/api/v1/admin/stock/{coupon_id}",
        )["stock"]

    def request(
        self,
        user_id: str,
        req_id: str,
        *,
        coupon_id: str = "COUPON_ACT_001",
        scene_name: str = "game",
        device: str = "mobile",
        policy_id: str = "",
        external: int = 0,
        score_threshold: float = 0.2,
        max_claim_per_request: int = 1,
    ) -> dict:
        self.cleanup_user(user_id)
        self.users.add(user_id)
        item = _FREE_SHIPPING_ITEM if coupon_id == "COUPON_SHIP_001" else _DISCOUNT_ITEM
        return {
            "user_id": user_id,
            "scene_name": scene_name,
            "device": device,
            "policy_id": policy_id,
            "external": external,
            "reqId": req_id,
            "score_threshold": score_threshold,
            "max_claim_per_request": max_claim_per_request,
            "context": {},
            "items": [copy.deepcopy(item)],
        }

    def post_recommend(self, body: dict) -> dict:
        return http_helper.post(self.http_base_url, "/api/v1/recommend", json=body)

    def post_recommend_response(self, body: dict):
        return http_helper.post_response(self.http_base_url, "/api/v1/recommend", json=body)

    def grpc_recommend(self, body: dict) -> dict:
        return grpc_ops.recommend(self.grpc_target, body)

    def query_coupons(self, user_id: str) -> dict:
        return http_helper.get(self.http_base_url, f"/api/v1/coupons/{user_id}")

    def close(self) -> None:
        for user_id in self.whitelist_users:
            try:
                http_helper.delete(self.ab_base_url, f"/api/v1/ab/whitelist/{user_id}")
            except Exception as exc:
                logger.warning("failed to remove e2e whitelist for %s: %s", user_id, exc)
        for user_id in self.users:
            self.cleanup_user(user_id)
        if self._redis_tracker is not None:
            self._redis_tracker.close()
