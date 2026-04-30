"""Rough ranking module fixtures."""
from __future__ import annotations

import copy
import os
import socket
import subprocess
import sys
import time
from concurrent import futures
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import grpc
import pytest
import yaml

from coupon_system.protos import scoring_pb2, scoring_pb2_grpc
from test_workspace.tests.helpers import grpc_ops
from test_workspace.tests.helpers import http as http_helper


AB_OFF = {"coarse_rank_exp_game": "cr_off", "calibration_exp_game": "cal_off"}
AB_ON = {"coarse_rank_exp_game": "cr_v2_full", "calibration_exp_game": "cal_off"}
COARSE_EXPERIMENT = "coarse_rank_exp_game"


DEFAULT_ITEMS = [
    {
        "item_id": "COUPON_RANK_A",
        "coupon_type": "discount",
        "value": 100,
        "min_spend": 9000,
        "expire_days": 7,
    },
    {
        "item_id": "COUPON_RANK_B",
        "coupon_type": "fixed",
        "value": 80,
        "min_spend": 1000,
        "expire_days": 7,
        "isPrior": True,
    },
    {
        "item_id": "COUPON_RANK_C",
        "coupon_type": "free_shipping",
        "value": 50,
        "min_spend": 500,
        "expire_days": 7,
    },
]


CASE_CONFIGS = {
    "TC-RANK-001": {"ab": AB_OFF, "params": {"enable_coarse_rank": False}},
    "TC-RANK-002": {"params": {"enable_coarse_rank": True, "truncate_count": 3}},
    "TC-RANK-003": {"params": {"enable_coarse_rank": True, "truncate_count": 2, "truncate_rule": "top_value"}},
    "TC-RANK-004": {"params": {"enable_coarse_rank": True, "truncate_count": 2, "truncate_rule": "top_min_spend"}},
    "TC-RANK-005": {"params": {"enable_coarse_rank": True, "truncate_count": 2, "truncate_rule": "random"}},
    "TC-RANK-006": {"params": {"enable_coarse_rank": True, "truncate_count": 2, "prior_count": 1, "prior_rule": "top_value", "truncate_rule": "top_value"}},
    "TC-RANK-007": {"params": {"enable_coarse_rank": True, "truncate_count": 3, "filters": [{"field": "value", "op": "gte", "value": 80}, {"field": "coupon_type", "op": "in", "value": ["discount", "fixed"]}]}},
    "TC-RANK-008": {"params": {"enable_coarse_rank": True, "truncate_count": 3, "sort_keys": [{"field": "value", "weight": 1.0}, {"field": "min_spend", "weight": -1.0}]}},
    "TC-RANK-009": {
        "params": {"enable_coarse_rank": True, "truncate_count": 3, "truncate_rule": "top_value", "diversity": {"enabled": True, "group_field": "coupon_type", "max_per_group": 1}},
        "items": [
            {"item_id": "COUPON_RANK_D1", "coupon_type": "discount", "value": 100, "min_spend": 1000, "expire_days": 7},
            {"item_id": "COUPON_RANK_D2", "coupon_type": "discount", "value": 90, "min_spend": 1000, "expire_days": 7},
            {"item_id": "COUPON_RANK_F1", "coupon_type": "fixed", "value": 80, "min_spend": 1000, "expire_days": 7},
            {"item_id": "COUPON_RANK_D3", "coupon_type": "discount", "value": 70, "min_spend": 1000, "expire_days": 7},
        ],
    },
    "TC-RANK-010": {"params": {"enable_coarse_rank": True, "truncate_count": 10, "truncate_rule": "top_value"}, "items": [DEFAULT_ITEMS[0]]},
    "TC-RANK-011": {"params": {"enable_coarse_rank": True, "truncate_count": 1, "prior_count": 1, "prior_rule": "top_value"}},
    "TC-RANK-012": {
        "params": {
            "enable_coarse_rank": True,
            "truncate_count": 5,
            "prior_count": 2,
            "prior_rule": "top_value",
            "filters": [{"field": "expire_days", "op": "gte", "value": 3}],
            "sort_keys": [{"field": "value", "weight": 1.0}],
            "diversity": {"enabled": True, "group_field": "coupon_type", "max_per_group": 1},
        },
        "items": [
            {"item_id": "P1", "coupon_type": "discount", "value": 1000, "min_spend": 1000, "expire_days": 7, "isPrior": True},
            {"item_id": "P2", "coupon_type": "fixed", "value": 900, "min_spend": 1000, "expire_days": 7, "isPrior": True},
            {"item_id": "P3", "coupon_type": "free_shipping", "value": 100, "min_spend": 1000, "expire_days": 7, "isPrior": True},
            {"item_id": "A", "coupon_type": "discount", "value": 800, "min_spend": 1000, "expire_days": 7},
            {"item_id": "B", "coupon_type": "discount", "value": 700, "min_spend": 1000, "expire_days": 1},
            {"item_id": "C", "coupon_type": "fixed", "value": 600, "min_spend": 1000, "expire_days": 7},
            {"item_id": "D", "coupon_type": "fixed", "value": 500, "min_spend": 1000, "expire_days": 1},
            {"item_id": "E", "coupon_type": "free_shipping", "value": 400, "min_spend": 1000, "expire_days": 7},
        ],
    },
    "TC-RANK-013": {"items": []},
    "TC-RANK-014": {"params": {"enable_coarse_rank": True, "truncate_count": 0, "truncate_rule": "top_value"}},
    "TC-RANK-015": {"params": {"enable_coarse_rank": True, "truncate_count": "bad", "truncate_rule": "top_value"}},
    "TC-RANK-016": {"params": {"enable_coarse_rank": True, "truncate_count": 2, "truncate_rule": "unknown_rule"}},
    "TC-RANK-017": {"params": {"enable_coarse_rank": True, "truncate_count": 2, "sort_keys": ["bad", {"field": 123, "weight": 1}, {"field": "value", "weight": "bad"}]}},
    "TC-RANK-018": {"params": {"enable_coarse_rank": True, "truncate_count": 3, "filters": [{"field": "value", "op": "bad_op", "value": 80}]}},
    "TC-RANK-019": {"params": {"enable_coarse_rank": True, "truncate_count": 2, "truncate_rule": "top_value", "diversity": {"enabled": True, "group_field": 123, "max_per_group": 0}}},
    "TC-RANK-020": {"params": {"enable_coarse_rank": True, "truncate_count": 1, "prior_count": 3, "prior_rule": "top_value"}},
    "TC-RANK-021": {"params": {"enable_coarse_rank": True, "truncate_count": "bad", "truncate_rule": "top_value"}},
    "TC-RANK-022": {"params": {"enable_coarse_rank": True, "truncate_count": 2, "truncate_rule": "unknown_rule"}},
    "TC-RANK-023": {"params": {"enable_coarse_rank": True, "truncate_count": 1, "prior_count": 3, "prior_rule": "top_value"}},
}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _RecordingScoringServicer(scoring_pb2_grpc.ScoringServiceServicer):
    def __init__(self) -> None:
        self.requests: list[list[str]] = []

    def Score(self, request, context):
        item_ids = [item.item_id for item in request.items]
        self.requests.append(item_ids)
        scores = [
            scoring_pb2.ItemScore(item_id=item_id, score=max(0.1, 0.9 - idx * 0.01))
            for idx, item_id in enumerate(item_ids)
        ]
        return scoring_pb2.ScoreResponse(code=0, message="success", scores=scores)


class RecordingScoringServer:
    def __init__(self) -> None:
        self.port = _free_port()
        self.servicer = _RecordingScoringServicer()
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
        scoring_pb2_grpc.add_ScoringServiceServicer_to_server(self.servicer, self.server)
        self.server.add_insecure_port(f"127.0.0.1:{self.port}")
        self.server.start()

    @property
    def last_items(self) -> list[str]:
        return self.servicer.requests[-1] if self.servicer.requests else []

    def stop(self) -> None:
        self.server.stop(grace=0)


@dataclass
class RoughRankingCase:
    case_id: str
    http_base_url: str
    grpc_target: str
    config: dict[str, Any]
    scoring: RecordingScoringServer

    @property
    def rank_input_items(self) -> list[str]:
        return self.scoring.last_items

    def recommend_http(self, user_id: str | None = None, req_id: str | None = None) -> dict:
        body = self.request_body(user_id=user_id, req_id=req_id)
        self._ensure_stock(body["items"])
        return http_helper.post(self.http_base_url, "/api/v1/recommend", json=body)

    def recommend_grpc(self, user_id: str | None = None, req_id: str | None = None) -> dict:
        body = self.request_body(user_id=user_id, req_id=req_id, grpc_items=True)
        self._ensure_stock(body["items"])
        return grpc_ops.recommend(self.grpc_target, body)

    def request_body(
        self,
        user_id: str | None = None,
        req_id: str | None = None,
        grpc_items: bool = False,
    ) -> dict:
        num = self.case_id.split("-")[-1].lower()
        items = copy.deepcopy(self.config.get("items", DEFAULT_ITEMS))
        if grpc_items:
            for item in items:
                if "isPrior" in item:
                    item["is_prior"] = item.pop("isPrior")
        return {
            "user_id": user_id or f"u_rank_{num}",
            "scene_name": "game",
            "device": "mobile",
            "policy_id": "",
            "external": 0,
            "reqId": req_id or f"req-rank-{num}",
            "score_threshold": 0.0,
            "max_claim_per_request": 1,
            "context": {},
            "items": items,
        }

    def _ensure_stock(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            http_helper.post(
                self.http_base_url,
                "/api/v1/admin/stock",
                json={"coupon_id": item["item_id"], "stock": 100, "ttl": 86400},
            )


def _write_case_config(tmp_path: Path, scoring_port: int) -> Path:
    settings = yaml.safe_load(Path("coupon_system/config/settings.yaml").read_text())
    settings["scoring_service"]["host"] = "127.0.0.1"
    settings["scoring_service"]["port"] = scoring_port
    config_path = tmp_path / "rough_settings.yaml"
    config_path.write_text(yaml.safe_dump(settings, allow_unicode=True), encoding="utf-8")
    return config_path


def _patch_strategy_params(experiment: dict, params: dict[str, Any]) -> dict:
    patched = copy.deepcopy(experiment)
    for strategy in patched["strategies"]:
        if strategy["id"] == "cr_v2_full":
            strategy["params"] = copy.deepcopy(params)
            break
    return patched


def _start_service(tmp_path: Path, scoring_port: int, ab_base_url: str) -> tuple[subprocess.Popen[str], str, str]:
    http_port = _free_port()
    grpc_port = _free_port()
    config_path = _write_case_config(tmp_path, scoring_port)
    env = os.environ.copy()
    env.update(
        {
            "HTTP_PORT": str(http_port),
            "GRPC_PORT": str(grpc_port),
            "COUPON_CONFIG_PATH": str(config_path),
            "AB_SERVICE_URL": ab_base_url,
            "NO_PROXY": "localhost,127.0.0.1",
            "no_proxy": "localhost,127.0.0.1",
        }
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "coupon_system.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    base_url = f"http://127.0.0.1:{http_port}"
    deadline = time.monotonic() + 20
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            output, _ = proc.communicate(timeout=5)
            raise RuntimeError(f"rough ranking service exited early:\n{output}")
        try:
            if http_helper.get(base_url, "/health", timeout=0.5).get("status") == "ok":
                return proc, base_url, f"127.0.0.1:{grpc_port}"
        except Exception as exc:
            last_error = exc
        time.sleep(0.2)
    proc.terminate()
    output, _ = proc.communicate(timeout=10)
    raise RuntimeError(f"rough ranking service did not become ready: {last_error}\n{output}")


@pytest.fixture
def setup_rough_ranking(ab_base_url, tmp_path, redis_tracker):
    """Prepare AB params, an isolated main service, and a recording scoring proxy."""
    original_experiment = None
    whitelist_users: list[str] = []
    processes: list[subprocess.Popen[str]] = []
    scorers: list[RecordingScoringServer] = []

    def _setup(case_id: str) -> RoughRankingCase:
        nonlocal original_experiment
        config = CASE_CONFIGS.get(case_id, {})
        num = case_id.split("-")[-1].lower()
        user_id = f"u_rank_{num}"

        if original_experiment is None:
            original_experiment = http_helper.get(ab_base_url, f"/api/v1/ab/experiments/{COARSE_EXPERIMENT}")

        params = config.get("params", {"enable_coarse_rank": True, "truncate_count": 3})
        http_helper.put(
            ab_base_url,
            f"/api/v1/ab/experiments/{COARSE_EXPERIMENT}",
            json=_patch_strategy_params(original_experiment, params),
        )

        strategy_map = config.get("ab", AB_ON)
        http_helper.put(ab_base_url, f"/api/v1/ab/whitelist/{user_id}", json={"strategy_map": strategy_map})
        whitelist_users.append(user_id)

        scoring = RecordingScoringServer()
        scorers.append(scoring)
        proc, base_url, grpc_target = _start_service(tmp_path, scoring.port, ab_base_url)
        processes.append(proc)
        return RoughRankingCase(case_id, base_url, grpc_target, config, scoring)

    yield _setup

    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=10)

    for scorer in scorers:
        scorer.stop()

    for user_id in whitelist_users:
        redis_tracker.delete(
            f"coupon:user:{user_id}:claimed",
            f"coupon:user:{user_id}:instances",
            f"coupon:rate:user:{user_id}",
        )
        try:
            http_helper.delete(ab_base_url, f"/api/v1/ab/whitelist/{user_id}")
        except Exception:
            pass

    if original_experiment is not None:
        http_helper.put(ab_base_url, f"/api/v1/ab/experiments/{COARSE_EXPERIMENT}", json=original_experiment)
