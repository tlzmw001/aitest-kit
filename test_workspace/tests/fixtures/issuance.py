"""Issuance module fixtures."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional

import pytest

from test_workspace.tests.helpers import grpc_ops
from test_workspace.tests.helpers import http as http_helper


AB_OFF = {"coarse_rank_exp_game": "cr_off", "calibration_exp_game": "cal_off"}

ITEM_A = {
    "item_id": "COUPON_ISSUE_A",
    "coupon_type": "discount",
    "value": 100,
    "min_spend": 5000,
    "expire_days": 7,
}
ITEM_B = {
    "item_id": "COUPON_ISSUE_B",
    "coupon_type": "fixed",
    "value": 80,
    "min_spend": 3000,
    "expire_days": 7,
}
ITEM_CONCURRENT = {
    "item_id": "COUPON_ISSUE_CONCURRENT",
    "coupon_type": "discount",
    "value": 50,
    "min_spend": 1000,
    "expire_days": 7,
}


def issue_item(item_id: str, expire_days: Optional[int] = 7) -> dict:
    items = {
        ITEM_A["item_id"]: ITEM_A,
        ITEM_B["item_id"]: ITEM_B,
        ITEM_CONCURRENT["item_id"]: ITEM_CONCURRENT,
    }
    item = copy.deepcopy(items[item_id])
    if expire_days is None:
        item.pop("expire_days", None)
    else:
        item["expire_days"] = expire_days
    return item


def issue_items(*item_ids: str) -> list[dict]:
    return [issue_item(item_id) for item_id in item_ids]


@dataclass
class IssuanceCase:
    http_base_url: str
    grpc_target: str
    ab_base_url: str
    redis_tracker: object
    users: set[str] = field(default_factory=set)

    def prepare_user(self, user_id: str) -> None:
        self.cleanup_user(user_id)
        http_helper.put(
            self.ab_base_url,
            f"/api/v1/ab/whitelist/{user_id}",
            json={"strategy_map": AB_OFF},
        )
        self.users.add(user_id)

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
        items: list[dict] | None = None,
        score_threshold: float = 0.0,
        max_claim_per_request: int = 1,
        policy_id: str = "",
    ) -> dict:
        self.prepare_user(user_id)
        return {
            "user_id": user_id,
            "scene_name": "game",
            "device": "mobile",
            "policy_id": policy_id,
            "external": 0,
            "reqId": req_id,
            "score_threshold": score_threshold,
            "max_claim_per_request": max_claim_per_request,
            "context": {},
            "items": copy.deepcopy(items if items is not None else issue_items("COUPON_ISSUE_A", "COUPON_ISSUE_B")),
        }

    def post_recommend(self, body: dict) -> dict:
        return http_helper.post(self.http_base_url, "/api/v1/recommend", json=body)

    def grpc_recommend(self, body: dict) -> dict:
        return grpc_ops.recommend(self.grpc_target, body)

    def query_coupons(self, user_id: str) -> dict:
        return http_helper.get(self.http_base_url, f"/api/v1/coupons/{user_id}")

    def grpc_query_coupons(self, user_id: str) -> dict:
        return grpc_ops.query_user_coupons(self.grpc_target, user_id)

    def teardown(self) -> None:
        for user_id in self.users:
            try:
                http_helper.delete(self.ab_base_url, f"/api/v1/ab/whitelist/{user_id}")
            except Exception:
                pass
            self.cleanup_user(user_id)


@pytest.fixture
def setup_issuance(http_base_url, grpc_target, ab_base_url, redis_tracker):
    """Prepare isolated stock, AB state, and user coupon state for issuance cases."""
    case = IssuanceCase(http_base_url, grpc_target, ab_base_url, redis_tracker)

    def _setup(case_id: str) -> IssuanceCase:
        for coupon_id in ("COUPON_ISSUE_A", "COUPON_ISSUE_B", "COUPON_ISSUE_CONCURRENT"):
            case.set_stock(coupon_id, 100)
        return case

    yield _setup
    case.teardown()
