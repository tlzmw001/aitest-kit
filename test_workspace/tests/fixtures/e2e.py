"""E2E module fixtures."""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field

import pytest

from test_workspace.tests.helpers import grpc_ops
from test_workspace.tests.helpers import http as http_helper


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

_CASE_WHITELIST_USERS = {
    "TC-E2E-001": "u_e2e_http_internal_001",
    "TC-E2E-004": "u_e2e_calibration_004",
}


@dataclass
class E2ECase:
    http_base_url: str
    grpc_target: str
    ab_base_url: str
    redis_tracker: object
    users: set[str] = field(default_factory=set)
    whitelist_users: set[str] = field(default_factory=set)

    def prepare_case(self, case_id: str) -> "E2ECase":
        whitelist_user = _CASE_WHITELIST_USERS.get(case_id)
        if whitelist_user:
            self.cleanup_user(whitelist_user)
            http_helper.put(
                self.ab_base_url,
                f"/api/v1/ab/whitelist/{whitelist_user}",
                json={"strategy_map": _E2E_WHITELIST},
            )
            self.users.add(whitelist_user)
            self.whitelist_users.add(whitelist_user)
        return self

    def cleanup_user(self, user_id: str) -> None:
        instance_set_key = f"coupon:user:{user_id}:instances"
        instance_ids = self.redis_tracker.smembers(instance_set_key)
        instance_keys = [f"coupon:instance:{iid}" for iid in instance_ids]
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

    def teardown(self) -> None:
        for user_id in self.whitelist_users:
            try:
                http_helper.delete(self.ab_base_url, f"/api/v1/ab/whitelist/{user_id}")
            except Exception as exc:
                logger.warning("failed to remove e2e whitelist for %s: %s", user_id, exc)
        for user_id in self.users:
            self.cleanup_user(user_id)


@pytest.fixture
def setup_e2e(http_base_url, grpc_target, ab_base_url, redis_tracker):
    """Prepare stock, AB whitelist, and observable state for end-to-end cases."""
    case = E2ECase(http_base_url, grpc_target, ab_base_url, redis_tracker)

    def _setup(case_id: str):
        return case.prepare_case(case_id)

    yield _setup
    case.teardown()
