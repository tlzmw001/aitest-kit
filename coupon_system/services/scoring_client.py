"""打分服务 gRPC 客户端 — 连接独立的打分 gRPC 服务"""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from typing import Optional

import grpc
import httpx

logger = logging.getLogger(__name__)

# 延迟导入编译后的 proto 模块
_scoring_pb2 = None
_scoring_pb2_grpc = None


def _lazy_import():
    global _scoring_pb2, _scoring_pb2_grpc
    if _scoring_pb2 is None:
        from coupon_system.protos import scoring_pb2, scoring_pb2_grpc
        _scoring_pb2 = scoring_pb2
        _scoring_pb2_grpc = scoring_pb2_grpc


@dataclass
class ItemScore:
    """打分结果"""
    item_id: str
    score: float


class ScoringClient:
    """打分服务客户端（内部 gRPC + 外部 HTTP）"""

    def __init__(
        self,
        host: str,
        port: int,
        timeout: float = 2.0,
        enabled: bool = True,
        external_host: str = "localhost",
        external_port: int = 50053,
        external_timeout: float = 2.0,
        external_enabled: bool = True,
        external_path: str = "/score",
        external_user_id_salt: str = "coupon_external_uid_salt",
    ):
        _lazy_import()
        self.host = host
        self.port = port
        self.timeout = timeout
        self.enabled = enabled
        self.external_host = external_host
        self.external_port = external_port
        self.external_timeout = external_timeout
        self.external_enabled = external_enabled
        self.external_path = external_path
        self.external_user_id_salt = external_user_id_salt
        self._channel = None
        self._stub = None

    def _get_stub(self):
        """延迟创建 gRPC channel 和 stub"""
        if self._stub is None:
            target = f"{self.host}:{self.port}"
            self._channel = grpc.insecure_channel(target)
            self._stub = _scoring_pb2_grpc.ScoringServiceStub(self._channel)
            logger.info("连接打分服务: %s", target)
        return self._stub

    def _external_url(self) -> str:
        path = self.external_path if self.external_path.startswith("/") else f"/{self.external_path}"
        return f"http://{self.external_host}:{self.external_port}{path}"

    def _encrypt_user_id(self, user_id: str) -> str:
        raw = f"{self.external_user_id_salt}:{user_id}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def score(
        self,
        user_id: str,
        scene_id: int,
        user_features: dict,
        context_features: dict,
        items: list,
        external: int = 0,
        request_id: Optional[str] = None,
    ) -> list:
        """
        调用打分服务。

        Args:
            user_id: 用户ID
            scene_id: 场景ID
            user_features: 用户特征 {name: value}
            context_features: 上下文特征 {name: value}
            items: [{item_id, features: {name: value}}]
            external: 0 走内部 gRPC，1 走外部 HTTP
            request_id: 请求 ID，缺省时自动生成

        Returns:
            list[ItemScore]: 打分结果

        Raises:
            TimeoutError: 打分服务超时
            RuntimeError: 打分服务不可用
        """
        rid = request_id or str(uuid.uuid4())

        if external == 1:
            return self._score_external_http(
                request_id=rid,
                user_id=user_id,
                scene_id=scene_id,
                user_features=user_features,
                context_features=context_features,
                items=items,
            )

        return self._score_internal_grpc(
            request_id=rid,
            user_id=user_id,
            scene_id=scene_id,
            user_features=user_features,
            context_features=context_features,
            items=items,
        )

    def _score_internal_grpc(
        self,
        request_id: str,
        user_id: str,
        scene_id: int,
        user_features: dict,
        context_features: dict,
        items: list,
    ) -> list:
        if not self.enabled:
            raise RuntimeError("Scoring service is disabled")

        stub = self._get_stub()

        # 构造请求
        item_messages = []
        for item in items:
            features_str = {k: str(v) for k, v in item.get("features", {}).items()}
            item_msg = _scoring_pb2.ItemFeatures(
                item_id=item["item_id"],
                features=features_str,
            )
            item_messages.append(item_msg)

        user_features_str = {k: str(v) for k, v in user_features.items()}
        context_features_str = {k: str(v) for k, v in context_features.items()}

        request = _scoring_pb2.ScoreRequest(
            request_id=request_id,
            user_id=user_id,
            scene_id=scene_id,
            user_features=user_features_str,
            context_features=context_features_str,
            items=item_messages,
        )

        try:
            response = stub.Score(request, timeout=self.timeout)
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                logger.error("打分服务超时: timeout=%.1fs", self.timeout)
                raise TimeoutError(f"Scoring service timeout: {self.timeout}s") from e
            logger.error("打分服务调用失败: %s", e)
            raise RuntimeError(f"Scoring service error: {e}") from e

        if response.code != 0:
            logger.error("打分服务返回错误: code=%d, msg=%s", response.code, response.message)
            raise RuntimeError(f"Scoring service error: {response.message}")

        return [
            ItemScore(item_id=s.item_id, score=s.score)
            for s in response.scores
        ]

    def _score_external_http(
        self,
        request_id: str,
        user_id: str,
        scene_id: int,
        user_features: dict,
        context_features: dict,
        items: list,
    ) -> list:
        if not self.external_enabled:
            raise RuntimeError("External scoring service is disabled")

        url = self._external_url()
        payload = {
            "request_id": request_id,
            "user_id": self._encrypt_user_id(user_id),
            "scene_id": scene_id,
            "user_features": {k: str(v) for k, v in user_features.items()},
            "context_features": {k: str(v) for k, v in context_features.items()},
            "items": [
                {
                    "item_id": item["item_id"],
                    "features": {k: str(v) for k, v in item.get("features", {}).items()},
                }
                for item in items
            ],
        }

        try:
            response = httpx.post(url, json=payload, timeout=self.external_timeout)
            response.raise_for_status()
        except httpx.TimeoutException as e:
            logger.error("外部打分服务超时: timeout=%.1fs url=%s", self.external_timeout, url)
            raise TimeoutError(f"External scoring service timeout: {self.external_timeout}s") from e
        except httpx.HTTPError as e:
            logger.error("外部打分服务调用失败: %s", e)
            raise RuntimeError(f"External scoring service error: {e}") from e

        try:
            body = response.json()
        except ValueError as e:
            logger.error("外部打分服务返回非 JSON: %s", response.text)
            raise RuntimeError("External scoring service returned invalid JSON") from e

        if int(body.get("code", 5000)) != 0:
            msg = body.get("message", "unknown")
            logger.error("外部打分服务返回错误: code=%s, msg=%s", body.get("code"), msg)
            raise RuntimeError(f"External scoring service error: {msg}")

        scores = body.get("scores", [])
        return [
            ItemScore(item_id=str(s["item_id"]), score=float(s["score"]))
            for s in scores
        ]

    def close(self):
        """关闭 gRPC channel"""
        if self._channel is not None:
            self._channel.close()
            self._channel = None
            self._stub = None
