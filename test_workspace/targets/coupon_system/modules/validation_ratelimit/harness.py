"""Reusable actions for coupon_system validation and rate-limit tests."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, ClassVar

import yaml

from aitest_kit.runtime_variables import require_env
from test_workspace.targets.coupon_system.helpers import grpc_ops
from test_workspace.targets.coupon_system.helpers import http as http_helper
from test_workspace.targets.coupon_system.helpers.redis_ops import RedisTracker


@dataclass
class ValidationRatelimitHarness:
    """Validation actions plus isolated service lifecycle for one test."""

    ERR: ClassVar[dict[str, Any]] = {
        "code": 1001,
        "message": "参数无效",
        "scene_id": 0,
        "experiment_info": {},
        "results": [],
        "coupon": None,
    }
    LIMITED: ClassVar[dict[str, Any]] = {
        "code": 1010,
        "message": "请求过于频繁，请稍后重试",
        "scene_id": 0,
        "experiment_info": {},
        "results": [],
        "coupon": None,
    }
    DEFAULT_ITEM: ClassVar[dict[str, Any]] = {
        "item_id": "COUPON_VAL_001",
        "coupon_type": "discount",
        "value": 80,
        "min_spend": 5000,
        "expire_days": 7,
    }
    BOUNDARY_ITEM: ClassVar[dict[str, Any]] = {
        "item_id": "COUPON_BOUNDARY_001",
        "coupon_type": "discount",
        "value": 80,
        "min_spend": 5000,
        "expire_days": 7,
    }
    _RATE_USERS: ClassVar[tuple[str, ...]] = (
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

    processes: list[subprocess.Popen[str]] = field(default_factory=list)
    _http_base_url: str | None = field(default=None, init=False)
    _grpc_target: str | None = field(default=None, init=False)
    _redis_tracker: RedisTracker | None = field(default=None, init=False)
    _temp_directory: TemporaryDirectory | None = field(default=None, init=False)

    @property
    def http_base_url(self) -> str:
        if self._http_base_url is None:
            self._http_base_url = require_env("HTTP_BASE_URL").rstrip("/")
        return self._http_base_url

    @http_base_url.setter
    def http_base_url(self, value: str) -> None:
        self._http_base_url = value.rstrip("/")

    @property
    def grpc_target(self) -> str:
        if self._grpc_target is None:
            self._grpc_target = require_env("GRPC_TARGET")
        return self._grpc_target

    @grpc_target.setter
    def grpc_target(self, value: str) -> None:
        self._grpc_target = value

    @cached_property
    def ab_base_url(self) -> str:
        return require_env("AB_SERVICE_URL").rstrip("/")

    @cached_property
    def config_source(self) -> Path:
        return Path(require_env("COUPON_CONFIG_PATH"))

    @property
    def redis_tracker(self) -> RedisTracker:
        if self._redis_tracker is None:
            self._redis_tracker = RedisTracker(url=require_env("REDIS_URL"))
        return self._redis_tracker

    @property
    def temp_dir(self) -> Path:
        if self._temp_directory is None:
            self._temp_directory = TemporaryDirectory(
                prefix="aitest-validation-ratelimit-"
            )
        return Path(self._temp_directory.name)

    def prepare_default_state(self) -> None:
        self.prepare_stock([self.DEFAULT_ITEM, self.BOUNDARY_ITEM])
        self.clear_rate_keys(*self._RATE_USERS)

    def use_isolated_rate_service(
        self,
        *,
        max_qps: int,
        per_user_qps: int,
        window_seconds: int,
    ) -> None:
        """Start and select an isolated service with explicit rate-limit settings."""
        self.clear_rate_keys(*self._RATE_USERS)
        http_port = _free_port()
        grpc_port = _free_port()
        config_path = self._write_rate_config(
            {
                "max_qps": max_qps,
                "per_user_qps": per_user_qps,
                "window_seconds": window_seconds,
            }
        )
        env = os.environ.copy()
        env.update(
            {
                "HTTP_PORT": str(http_port),
                "GRPC_PORT": str(grpc_port),
                "COUPON_CONFIG_PATH": str(config_path),
                "AB_SERVICE_URL": self.ab_base_url,
                "NO_PROXY": "localhost,127.0.0.1",
                "no_proxy": "localhost,127.0.0.1",
            }
        )
        process = subprocess.Popen(
            [sys.executable, "-m", "coupon_system.main"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        self.processes.append(process)
        base_url = f"http://127.0.0.1:{http_port}"
        self._wait_until_ready(process, base_url)
        self.http_base_url = base_url
        self.grpc_target = f"127.0.0.1:{grpc_port}"
        self.prepare_stock([self.DEFAULT_ITEM, self.BOUNDARY_ITEM])

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
            "items": [dict(item or self.DEFAULT_ITEM)],
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
        for field_name in fields:
            body.pop(field_name, None)
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

    def close(self) -> None:
        for process in self.processes:
            if process.poll() is not None:
                continue
            process.terminate()
            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=10)
        if self._redis_tracker is not None:
            self._redis_tracker.close()
        if self._temp_directory is not None:
            self._temp_directory.cleanup()

    def _write_rate_config(self, rate_config: dict[str, int]) -> Path:
        settings = yaml.safe_load(self.config_source.read_text(encoding="utf-8"))
        settings["rate_limit"]["enabled"] = True
        settings["rate_limit"].update(rate_config)
        config_path = self.temp_dir / f"validation_settings_{len(self.processes)}.yaml"
        config_path.write_text(
            yaml.safe_dump(settings, allow_unicode=True),
            encoding="utf-8",
        )
        return config_path

    @staticmethod
    def _wait_until_ready(process: subprocess.Popen[str], base_url: str) -> None:
        deadline = time.monotonic() + 20
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output, _ = process.communicate(timeout=5)
                raise RuntimeError(f"validation rate service exited early:\n{output}")
            try:
                if http_helper.get(base_url, "/health", timeout=0.5).get("status") == "ok":
                    return
            except Exception as exc:
                last_error = exc
            time.sleep(0.2)
        raise RuntimeError(
            f"validation rate service did not become ready: {last_error}"
        )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
