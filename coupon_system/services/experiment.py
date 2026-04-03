"""AB 实验分流模块 — 根据 uid hash 确定实验策略"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional

from coupon_system.config import ExperimentConfig, ExperimentStrategy

logger = logging.getLogger(__name__)


@dataclass
class ExperimentResult:
    """单个实验的分流结果"""
    experiment_name: str
    strategy_id: str
    params: dict = field(default_factory=dict)


class ExperimentRouter:
    """AB 实验路由器：对每个实验，hash(uid) 落入某个策略的 hash_range"""

    def __init__(self, config: ExperimentConfig):
        self.config = config

    def route(self, user_id: str) -> dict:
        """
        对所有实验进行分流。

        Args:
            user_id: 用户ID

        Returns:
            dict[str, ExperimentResult]: {实验名: 分流结果}
        """
        results = {}
        hash_value = self._hash_uid(user_id)

        for experiment in self.config.experiments:
            strategy = self._match_strategy(hash_value, experiment.strategies)
            if strategy is not None:
                results[experiment.name] = ExperimentResult(
                    experiment_name=experiment.name,
                    strategy_id=strategy.id,
                    params=dict(strategy.params),
                )
            else:
                logger.warning(
                    "user_id=%s hash=%d 未命中实验 %s 的任何策略",
                    user_id, hash_value, experiment.name,
                )

        return results

    def _hash_uid(self, user_id: str) -> int:
        """uid hash → [0, 100) 的整数"""
        digest = hashlib.md5(user_id.encode()).hexdigest()
        return int(digest, 16) % 100

    def _match_strategy(
        self, hash_value: int, strategies: list
    ) -> Optional[ExperimentStrategy]:
        """根据 hash 值匹配策略"""
        for strategy in strategies:
            low, high = strategy.hash_range
            if low <= hash_value < high:
                return strategy
        return None
