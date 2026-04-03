"""Mock 打分 gRPC 服务 — 独立进程运行，模拟 ML 打分"""
from __future__ import annotations

import logging
import os
import random
import signal
import subprocess
import sys
import time
from concurrent import futures
from pathlib import Path

import grpc
from grpc_reflection.v1alpha import reflection

logger = logging.getLogger(__name__)

# 延迟导入
_pb2 = None
_pb2_grpc = None


def _ensure_proto_compiled():
    """确保 scoring proto 已编译"""
    global _pb2, _pb2_grpc
    if _pb2 is not None:
        return

    proto_dir = Path(__file__).parent.parent / "protos"
    pb2_file = proto_dir / "scoring_pb2.py"
    proto_file = proto_dir / "scoring.proto"

    if not pb2_file.exists() or pb2_file.stat().st_mtime < proto_file.stat().st_mtime:
        print("Compiling scoring.proto...")
        result = subprocess.run(
            [
                sys.executable, "-m", "grpc_tools.protoc",
                f"--proto_path={proto_dir}",
                f"--python_out={proto_dir}",
                f"--grpc_python_out={proto_dir}",
                str(proto_file),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Proto compilation failed: {result.stderr}")
            sys.exit(1)

        # 修复 import 路径
        grpc_file = proto_dir / "scoring_pb2_grpc.py"
        if grpc_file.exists():
            content = grpc_file.read_text()
            content = content.replace(
                "import scoring_pb2 as scoring__pb2",
                "from coupon_system.protos import scoring_pb2 as scoring__pb2",
            )
            grpc_file.write_text(content)

        print("scoring.proto compilation done.")

    from coupon_system.protos import scoring_pb2, scoring_pb2_grpc
    _pb2 = scoring_pb2
    _pb2_grpc = scoring_pb2_grpc


class MockScorer:
    """Mock 评分逻辑：基于特征计算分数"""

    def __init__(self):
        self._simulate_failure = False
        self._simulate_timeout = False
        self._timeout_seconds = 5.0

    def score(self, user_features: dict, context_features: dict, items: list) -> list:
        """
        对每个 item 计算 mock 分数。

        Args:
            user_features: 用户特征
            context_features: 上下文特征
            items: [{item_id, features}]

        Returns:
            list of (item_id, score)
        """
        if self._simulate_failure:
            raise RuntimeError("Mock scoring service unavailable")

        if self._simulate_timeout:
            time.sleep(self._timeout_seconds)
            raise TimeoutError("Mock scoring service timeout")

        results = []
        for item in items:
            score = self._calculate_score(user_features, item.get("features", {}))
            results.append((item["item_id"], round(score, 4)))
        return results

    def _calculate_score(self, user_features: dict, item_features: dict) -> float:
        """基于特征计算 mock 分数"""
        base_score = 0.1

        # 用户特征加分
        if str(user_features.get("is_new_user", "")).lower() == "true":
            base_score += 0.15
        if str(user_features.get("is_member", "")).lower() == "true":
            base_score += 0.1

        total_spend = float(user_features.get("total_spend", 0))
        if total_spend > 10000:
            base_score += 0.1
        elif total_spend > 5000:
            base_score += 0.05

        # item 特征加分
        popularity = float(item_features.get("popularity", 0))
        base_score += popularity * 0.1

        # 随机噪声
        noise = random.uniform(-0.05, 0.05)
        return max(0.0, min(1.0, base_score + noise))

    def set_simulate_failure(self, enabled: bool) -> None:
        self._simulate_failure = enabled

    def set_simulate_timeout(self, enabled: bool, timeout: float = 5.0) -> None:
        self._simulate_timeout = enabled
        self._timeout_seconds = timeout


class ScoringServicer:
    """gRPC Servicer 实现"""

    def __init__(self, scorer: MockScorer):
        self.scorer = scorer

    def Score(self, request, context):
        """处理打分请求"""
        try:
            user_features = dict(request.user_features)
            context_features = dict(request.context_features)

            items = []
            for item in request.items:
                items.append({
                    "item_id": item.item_id,
                    "features": dict(item.features),
                })

            results = self.scorer.score(user_features, context_features, items)

            item_scores = [
                _pb2.ItemScore(item_id=item_id, score=score)
                for item_id, score in results
            ]

            return _pb2.ScoreResponse(
                code=0,
                message="success",
                scores=item_scores,
            )

        except (TimeoutError, RuntimeError) as e:
            logger.error("打分服务异常: %s", e)
            return _pb2.ScoreResponse(
                code=5000,
                message=str(e),
                scores=[],
            )


def serve(port: int = 50052):
    """启动 mock 打分 gRPC 服务"""
    _ensure_proto_compiled()

    scorer = MockScorer()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = ScoringServicer(scorer)
    _pb2_grpc.add_ScoringServiceServicer_to_server(servicer, server)

    # Server Reflection
    service_names = (
        _pb2.DESCRIPTOR.services_by_name["ScoringService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"Mock scoring server started on port {port}")

    def shutdown(signum, frame):
        print("\nShutting down scoring server...")
        server.stop(grace=5)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    server.wait_for_termination()


if __name__ == "__main__":
    port = int(os.environ.get("SCORING_PORT", "50052"))
    logging.basicConfig(level=logging.INFO)
    serve(port)
