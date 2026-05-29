"""Validation and rate-limit module fixtures."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pytest
import yaml

from test_workspace.targets.coupon_system.helpers import grpc_ops
from test_workspace.targets.coupon_system.helpers import http as http_helper


ERR = {
    "code": 1001,
    "message": "参数无效",
    "scene_id": 0,
    "experiment_info": {},
    "results": [],
    "coupon": None,
}

LIMITED = {
    "code": 1010,
    "message": "请求过于频繁，请稍后重试",
    "scene_id": 0,
    "experiment_info": {},
    "results": [],
    "coupon": None,
}

DEFAULT_ITEM = {
    "item_id": "COUPON_VAL_001",
    "coupon_type": "discount",
    "value": 80,
    "min_spend": 5000,
    "expire_days": 7,
}

BOUNDARY_ITEM = {
    "item_id": "COUPON_BOUNDARY_001",
    "coupon_type": "discount",
    "value": 80,
    "min_spend": 5000,
    "expire_days": 7,
}

RATE_CONFIGS = {
    "TC-RATE-001": {"max_qps": 100, "per_user_qps": 2, "window_seconds": 1},
    "TC-RATE-002": {"max_qps": 2, "per_user_qps": 10, "window_seconds": 1},
    "TC-RATE-003": {"max_qps": 2, "per_user_qps": 10, "window_seconds": 1},
    "TC-RATE-004": {"max_qps": 100, "per_user_qps": 1, "window_seconds": 1},
    "TC-RATE-005": {"max_qps": 100, "per_user_qps": 1, "window_seconds": 1},
    "TC-RATE-006": {"max_qps": 100, "per_user_qps": 1, "window_seconds": 1},
    "TC-RATE-007": {"max_qps": 100, "per_user_qps": 1, "window_seconds": 1},
}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass
class ValidationCase:
    case_id: str
    http_base_url: str
    grpc_target: str
    redis_tracker: Any

    def body(
        self,
        user_id: str,
        req_id: str,
        *,
        item: dict[str, Any] | None = None,
        **overrides,
    ) -> dict:
        body = {
            "user_id": user_id,
            "scene_name": "game",
            "device": "mobile",
            "policy_id": "",
            "external": 0,
            "reqId": req_id,
            "score_threshold": 0.0,
            "max_claim_per_request": 1,
            "context": {},
            "items": [dict(item or DEFAULT_ITEM)],
        }
        body.update(overrides)
        return body

    def http(self, user_id: str, req_id: str, **overrides) -> dict:
        body = self.body(user_id, req_id, **overrides)
        self.prepare_stock(body["items"])
        return http_helper.post(self.http_base_url, "/api/v1/recommend", json=body)

    def http_response(self, body: dict) -> Any:
        self.prepare_stock(body.get("items", []))
        return http_helper.post_response(self.http_base_url, "/api/v1/recommend", json=body)

    def grpc(self, user_id: str, req_id: str, **overrides) -> dict:
        body = self.body(user_id, req_id, **overrides)
        self.prepare_stock(body["items"])
        return grpc_ops.recommend(self.grpc_target, body)

    def grpc_missing(self, user_id: str, req_id: str, *fields: str) -> dict:
        body = self.body(user_id, req_id, score_threshold=0.5)
        for field in fields:
            body.pop(field, None)
        self.prepare_stock(body["items"])
        return grpc_ops.recommend(self.grpc_target, body)

    def prepare_stock(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            item_id = item.get("item_id")
            if not item_id:
                continue
            http_helper.post(
                self.http_base_url,
                "/api/v1/admin/stock",
                json={"coupon_id": item_id, "stock": 100, "ttl": 86400},
            )

    def clear_rate_keys(self, *user_ids: str) -> None:
        keys = ["coupon:rate:global"]
        keys.extend(f"coupon:rate:user:{user_id}" for user_id in user_ids)
        self.redis_tracker.delete(*keys)

    def wait_rate_key_gone(self, user_id: str, timeout: float = 3.0) -> None:
        key = f"coupon:rate:user:{user_id}"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.redis_tracker.exists(key):
                return
            time.sleep(0.1)
        raise AssertionError(f"rate key did not expire: {key}")


def _write_rate_config(tmp_path: Path, rate_config: dict[str, int]) -> Path:
    settings = yaml.safe_load(Path("coupon_system/config/settings.yaml").read_text())
    settings["rate_limit"]["enabled"] = True
    settings["rate_limit"]["max_qps"] = rate_config["max_qps"]
    settings["rate_limit"]["per_user_qps"] = rate_config["per_user_qps"]
    settings["rate_limit"]["window_seconds"] = rate_config["window_seconds"]
    config_path = tmp_path / "validation_settings.yaml"
    config_path.write_text(yaml.safe_dump(settings, allow_unicode=True), encoding="utf-8")
    return config_path


def _start_service(tmp_path: Path, ab_base_url: str, rate_config: dict[str, int]) -> tuple[subprocess.Popen[str], str, str]:
    http_port = _free_port()
    grpc_port = _free_port()
    config_path = _write_rate_config(tmp_path, rate_config)
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
            raise RuntimeError(f"validation rate service exited early:\n{output}")
        try:
            if http_helper.get(base_url, "/health", timeout=0.5).get("status") == "ok":
                return proc, base_url, f"127.0.0.1:{grpc_port}"
        except Exception as exc:
            last_error = exc
        time.sleep(0.2)
    proc.terminate()
    output, _ = proc.communicate(timeout=10)
    raise RuntimeError(f"validation rate service did not become ready: {last_error}\n{output}")


@pytest.fixture
def setup_validation_ratelimit(
    http_base_url,
    grpc_target,
    ab_base_url,
    tmp_path,
    redis_tracker,
) -> Callable[[str], ValidationCase]:
    """Return a case factory that prepares stock, rate keys, and isolated services."""
    processes: list[subprocess.Popen[str]] = []

    def _setup(case_id: str) -> ValidationCase:
        if case_id in RATE_CONFIGS:
            proc, base_url, target = _start_service(tmp_path, ab_base_url, RATE_CONFIGS[case_id])
            processes.append(proc)
            case = ValidationCase(case_id, base_url, target, redis_tracker)
        else:
            case = ValidationCase(case_id, http_base_url, grpc_target, redis_tracker)

        case.prepare_stock([DEFAULT_ITEM, BOUNDARY_ITEM])
        case.clear_rate_keys(
            "u_val_001",
            "u_val_002",
            "u_val_003",
            "u_val_004",
            "u_val_005",
            "u_val_006",
            "u_val_007",
            "u_rate_old_user",
            "u_rate_http_user",
            "u_rate_grpc_user",
            "u_rate_http_window",
            "u_rate_grpc_window",
            "u_rate_http_global_1",
            "u_rate_http_global_2",
            "u_rate_http_global_3",
            "u_rate_grpc_global_1",
            "u_rate_grpc_global_2",
            "u_rate_grpc_global_3",
        )
        return case

    yield _setup

    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=10)
