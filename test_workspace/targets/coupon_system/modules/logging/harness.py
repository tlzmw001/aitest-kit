"""Actions and subprocess lifecycle for coupon logging tests."""
from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from test_workspace.targets.coupon_system.helpers import grpc_ops
from test_workspace.targets.coupon_system.helpers import http as http_helper

LOG_ITEMS = [
    {
        "item_id": "COUPON_LOG_001",
        "coupon_type": "discount",
        "value": 80,
        "min_spend": 5000,
        "expire_days": 7,
    },
    {
        "item_id": "COUPON_LOG_002",
        "coupon_type": "fixed",
        "value": 5000,
        "min_spend": 20000,
        "expire_days": 7,
    },
]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass
class LoggingHarness:
    ab_base_url: str
    redis_url: str
    process: subprocess.Popen[str] | None = None
    http_base_url: str = ""
    grpc_target: str = ""
    _logs: str = ""
    _stocked: set[str] = field(default_factory=set)

    def request(
        self,
        user_id: str,
        req_id: str,
        *,
        external: int = 0,
        policy_id: str = "",
        items: list[dict[str, Any]] | None = None,
    ) -> dict:
        body = self.body(
            user_id=user_id,
            req_id=req_id,
            external=external,
            policy_id=policy_id,
            items=items,
        )
        self._ensure_stock(body["items"])
        return http_helper.post(self.http_base_url, "/api/v1/recommend", json=body)

    def grpc_request(
        self,
        user_id: str,
        req_id: str,
        *,
        external: int = 0,
        policy_id: str = "",
        items: list[dict[str, Any]] | None = None,
    ) -> dict:
        body = self.body(
            user_id=user_id,
            req_id=req_id,
            external=external,
            policy_id=policy_id,
            items=items,
        )
        self._ensure_stock(body["items"])
        return grpc_ops.recommend(self.grpc_target, body)

    def run_http_with_logs(
        self,
        *,
        user_id: str,
        req_id: str,
        external: int = 0,
        policy_id: str = "",
        items: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self.start_with_info_logging()
        response = self.request(
            user_id=user_id,
            req_id=req_id,
            external=external,
            policy_id=policy_id,
            items=items,
        )
        return {"resp": response, "logs": self.stop_and_logs()}

    def run_grpc_with_logs(
        self,
        *,
        user_id: str,
        req_id: str,
        external: int = 0,
        policy_id: str = "",
        items: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self.start_with_info_logging()
        response = self.grpc_request(
            user_id=user_id,
            req_id=req_id,
            external=external,
            policy_id=policy_id,
            items=items,
        )
        return {"resp": response, "logs": self.stop_and_logs()}

    def has_auto_req_id_log(self, logs: str) -> bool:
        return bool(
            re.search(
                r"recommend request: reqId=[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                logs,
            )
        )

    def body(
        self,
        user_id: str,
        req_id: str,
        *,
        external: int = 0,
        policy_id: str = "",
        items: list[dict[str, Any]] | None = None,
    ) -> dict:
        return {
            "user_id": user_id,
            "scene_name": "game",
            "device": "mobile",
            "policy_id": policy_id,
            "external": external,
            "reqId": req_id,
            "score_threshold": 0.0,
            "max_claim_per_request": 1,
            "context": {},
            "items": items or [dict(item) for item in LOG_ITEMS],
        }

    def start_with_info_logging(self) -> None:
        if self.process is not None:
            return
        http_port = _free_port()
        grpc_port = _free_port()
        self.http_base_url = f"http://127.0.0.1:{http_port}"
        self.grpc_target = f"127.0.0.1:{grpc_port}"
        env = os.environ.copy()
        env.update(
            {
                "HTTP_PORT": str(http_port),
                "GRPC_PORT": str(grpc_port),
                "AB_SERVICE_URL": self.ab_base_url,
                "REDIS_URL": self.redis_url,
                "NO_PROXY": "localhost,127.0.0.1",
                "no_proxy": "localhost,127.0.0.1",
            }
        )
        script = (
            "import logging; "
            "logging.basicConfig(level=logging.INFO); "
            "from coupon_system.main import main; "
            "main()"
        )
        self.process = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        self._wait_until_ready()

    def stop_and_logs(self) -> str:
        if self.process is None:
            return self._logs
        process = self.process
        self.process = None
        process.terminate()
        try:
            output, _ = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate(timeout=10)
        self._logs += output or ""
        return self._logs

    def close(self) -> None:
        self.stop_and_logs()

    def _wait_until_ready(self) -> None:
        assert self.process is not None
        deadline = time.monotonic() + 20
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                logs = self.stop_and_logs()
                raise RuntimeError(f"logging test service exited early:\n{logs}")
            try:
                health = http_helper.get(self.http_base_url, "/health", timeout=0.5)
                if health.get("status") == "ok":
                    return
            except Exception as exc:
                last_error = exc
            time.sleep(0.2)
        logs = self.stop_and_logs()
        raise RuntimeError(
            f"logging test service did not become ready: {last_error}\n{logs}"
        )

    def _ensure_stock(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            item_id = str(item["item_id"])
            if item_id in self._stocked:
                continue
            http_helper.post(
                self.http_base_url,
                "/api/v1/admin/stock",
                json={"coupon_id": item_id, "stock": 100, "ttl": 86400},
            )
            self._stocked.add(item_id)
