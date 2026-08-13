"""Public module Harness for rough-ranking tests."""
from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

from test_workspace.targets.coupon_system.helpers import grpc_ops
from test_workspace.targets.coupon_system.helpers import http as http_helper
from test_workspace.targets.coupon_system.helpers.redis_ops import RedisTracker
from test_workspace.targets.coupon_system.modules.rough_ranking.config_management import patch_strategy_params
from test_workspace.targets.coupon_system.modules.rough_ranking.resources import (
    DEFAULT_ITEMS,
    RecordingScoringServer,
    RunningCouponService,
    start_coupon_service,
)


AB_ON = {"coarse_rank_exp_game": "cr_v2_full", "calibration_exp_game": "cal_off"}
COARSE_EXPERIMENT = "coarse_rank_exp_game"
DEFAULT_PARAMS = {"enable_coarse_rank": True, "truncate_count": 3}

logger = logging.getLogger(__name__)


class RoughRankingHarness:
    """Prepare explicit rough-ranking state and exercise HTTP/gRPC entry points."""

    def __init__(self, *, ab_base_url: str, redis_tracker: RedisTracker, workspace: Path) -> None:
        self.ab_base_url = ab_base_url.rstrip("/")
        self.redis_tracker = redis_tracker
        self.workspace = workspace
        self._original_experiment: dict[str, Any] | None = None
        self._whitelist_users: list[str] = []
        self._scoring: RecordingScoringServer | None = None
        self._service: RunningCouponService | None = None
        self._items: list[dict[str, Any]] = []
        self._user_id = ""
        self._request_id = ""

    def prepare(
        self,
        *,
        user_id: str,
        request_id: str,
        params: dict[str, Any] | None = None,
        strategy_map: dict[str, str] | None = None,
        items: list[dict[str, Any]] | None = None,
    ) -> None:
        if self._service is not None:
            raise RuntimeError("rough-ranking Harness can prepare only once per test")
        self._snapshot_experiment()
        payload = patch_strategy_params(
            self._original_experiment or {},
            copy.deepcopy(params if params is not None else DEFAULT_PARAMS),
        )
        http_helper.put(
            self.ab_base_url,
            f"/api/v1/ab/experiments/{COARSE_EXPERIMENT}",
            json=payload,
        )
        http_helper.put(
            self.ab_base_url,
            f"/api/v1/ab/whitelist/{user_id}",
            json={"strategy_map": strategy_map if strategy_map is not None else AB_ON},
        )
        self._whitelist_users.append(user_id)
        self._items = copy.deepcopy(DEFAULT_ITEMS if items is None else items)
        self._user_id = user_id
        self._request_id = request_id
        self._scoring = RecordingScoringServer()
        self._service = start_coupon_service(self.workspace, self._scoring.port, self.ab_base_url)

    @property
    def rank_input_items(self) -> list[str]:
        return self._scoring.last_items if self._scoring is not None else []

    def recommend_http(self) -> dict[str, Any]:
        service = self._require_prepared()
        body = self.request_body()
        self._ensure_stock(service.base_url, body["items"])
        return http_helper.post(service.base_url, "/api/v1/recommend", json=body)

    def recommend_grpc(self) -> dict[str, Any]:
        service = self._require_prepared()
        body = self.request_body(grpc_items=True)
        self._ensure_stock(service.base_url, body["items"])
        return grpc_ops.recommend(service.grpc_target, body)

    def request_body(self, *, grpc_items: bool = False) -> dict[str, Any]:
        items = copy.deepcopy(self._items)
        if grpc_items:
            for item in items:
                if "isPrior" in item:
                    item["is_prior"] = item.pop("isPrior")
        return {
            "user_id": self._user_id,
            "scene_name": "game",
            "device": "mobile",
            "policy_id": "",
            "external": 0,
            "reqId": self._request_id,
            "score_threshold": 0.0,
            "max_claim_per_request": 1,
            "context": {},
            "items": items,
        }

    def close(self) -> None:
        errors: list[Exception] = []

        def attempt(label: str, action) -> None:
            try:
                action()
            except Exception as exc:
                logger.warning("rough-ranking cleanup failed for %s: %s", label, exc)
                errors.append(exc)

        if self._service is not None:
            attempt("coupon service", self._service.close)
        if self._scoring is not None:
            attempt("scoring service", self._scoring.close)
        for user_id in self._whitelist_users:
            attempt(
                f"Redis state for {user_id}",
                lambda user_id=user_id: self.redis_tracker.delete(
                    f"coupon:user:{user_id}:claimed",
                    f"coupon:user:{user_id}:instances",
                    f"coupon:rate:user:{user_id}",
                ),
            )
            attempt(
                f"AB whitelist for {user_id}",
                lambda user_id=user_id: http_helper.delete(
                    self.ab_base_url,
                    f"/api/v1/ab/whitelist/{user_id}",
                ),
            )
        if self._original_experiment is not None:
            attempt(
                "AB experiment restore",
                lambda: http_helper.put(
                    self.ab_base_url,
                    f"/api/v1/ab/experiments/{COARSE_EXPERIMENT}",
                    json=self._original_experiment,
                ),
            )
        if errors:
            raise errors[0]

    def _snapshot_experiment(self) -> None:
        if self._original_experiment is None:
            self._original_experiment = http_helper.get(
                self.ab_base_url,
                f"/api/v1/ab/experiments/{COARSE_EXPERIMENT}",
            )

    def _require_prepared(self) -> RunningCouponService:
        if self._service is None:
            raise RuntimeError("call harness.prepare(...) before sending a request")
        return self._service

    @staticmethod
    def _ensure_stock(base_url: str, items: list[dict[str, Any]]) -> None:
        for item in items:
            http_helper.post(
                base_url,
                "/api/v1/admin/stock",
                json={"coupon_id": item["item_id"], "stock": 100, "ttl": 86400},
            )
