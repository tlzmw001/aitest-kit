"""Process and scoring resources for rough-ranking integration tests."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from concurrent import futures
from pathlib import Path

import grpc
import yaml

from coupon_system.protos import scoring_pb2, scoring_pb2_grpc
from test_workspace.targets.coupon_system.helpers import http as http_helper


DEFAULT_ITEMS = [
    {"item_id": "COUPON_RANK_A", "coupon_type": "discount", "value": 100, "min_spend": 9000, "expire_days": 7},
    {"item_id": "COUPON_RANK_B", "coupon_type": "fixed", "value": 80, "min_spend": 1000, "expire_days": 7, "isPrior": True},
    {"item_id": "COUPON_RANK_C", "coupon_type": "free_shipping", "value": 50, "min_spend": 500, "expire_days": 7},
]


def free_port() -> int:
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
            scoring_pb2.ItemScore(item_id=item_id, score=max(0.1, 0.9 - index * 0.01))
            for index, item_id in enumerate(item_ids)
        ]
        return scoring_pb2.ScoreResponse(code=0, message="success", scores=scores)


class RecordingScoringServer:
    def __init__(self) -> None:
        self.port = free_port()
        self.servicer = _RecordingScoringServicer()
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
        scoring_pb2_grpc.add_ScoringServiceServicer_to_server(self.servicer, self.server)
        self.server.add_insecure_port(f"127.0.0.1:{self.port}")
        self.server.start()

    @property
    def last_items(self) -> list[str]:
        return self.servicer.requests[-1] if self.servicer.requests else []

    def close(self) -> None:
        self.server.stop(grace=0)


class RunningCouponService:
    def __init__(self, process: subprocess.Popen[str], base_url: str, grpc_target: str) -> None:
        self.process = process
        self.base_url = base_url
        self.grpc_target = grpc_target

    def close(self) -> None:
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.communicate(timeout=10)


def start_coupon_service(workspace: Path, scoring_port: int, ab_base_url: str) -> RunningCouponService:
    http_port = free_port()
    grpc_port = free_port()
    config_path = _write_service_config(workspace, scoring_port)
    env = os.environ.copy()
    env.update({
        "HTTP_PORT": str(http_port),
        "GRPC_PORT": str(grpc_port),
        "COUPON_CONFIG_PATH": str(config_path),
        "AB_SERVICE_URL": ab_base_url,
        "NO_PROXY": "localhost,127.0.0.1",
        "no_proxy": "localhost,127.0.0.1",
    })
    process = subprocess.Popen(
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
        if process.poll() is not None:
            output, _ = process.communicate(timeout=5)
            raise RuntimeError(f"rough ranking service exited early:\n{output}")
        try:
            if http_helper.get(base_url, "/health", timeout=0.5).get("status") == "ok":
                return RunningCouponService(process, base_url, f"127.0.0.1:{grpc_port}")
        except Exception as exc:
            last_error = exc
        time.sleep(0.2)
    process.terminate()
    output, _ = process.communicate(timeout=10)
    raise RuntimeError(f"rough ranking service did not become ready: {last_error}\n{output}")


def _write_service_config(workspace: Path, scoring_port: int) -> Path:
    settings = yaml.safe_load(Path("coupon_system/config/settings.yaml").read_text())
    settings["scoring_service"].update({"host": "127.0.0.1", "port": scoring_port})
    config_path = workspace / "rough_settings.yaml"
    config_path.write_text(yaml.safe_dump(settings, allow_unicode=True), encoding="utf-8")
    return config_path
