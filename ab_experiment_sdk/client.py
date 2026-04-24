"""AB 实验 SDK 协议与默认实现。"""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from typing import Optional, Protocol

from ab_experiment_sdk.models import ExperimentConfig, ExperimentStrategy

logger = logging.getLogger(__name__)


@dataclass
class ABExperimentRequest:
    """业务服务请求 AB SDK 的统一协议。"""

    user_id: str
    request_id: str = ""
    context: dict = field(default_factory=dict)
    experiment_names: Optional[list[str]] = None


@dataclass
class ABExperimentAssignment:
    """单个实验命中结果。"""

    experiment_name: str
    strategy_id: str
    params: dict = field(default_factory=dict)
    hit_reason: str = "hash"


@dataclass
class ABExperimentResponse:
    """AB SDK 返回结构。"""

    request_id: str
    user_id: str
    assignments: dict = field(default_factory=dict)
    trace_id: str = ""


class ABExperimentSDK(Protocol):
    """AB SDK 协议：业务系统只依赖该接口。"""

    def evaluate(self, request: ABExperimentRequest) -> ABExperimentResponse:
        ...

    def set_whitelist(self, whitelist: dict) -> None:
        ...

    def set_user_whitelist(self, user_id: str, strategy_map: dict) -> None:
        ...

    def clear_whitelist(self, user_id: Optional[str] = None) -> None:
        ...

    def get_whitelist(self) -> dict:
        ...


class ConfigBasedABExperimentSDK:
    """
    本地可运行的 AB SDK 实现。

    设计上模拟“外部依赖”的交互形式：业务只传 request，SDK 返回统一 response。
    分流优先级：白名单 > hash 分流。
    """

    def __init__(self, config: ExperimentConfig, whitelist: Optional[dict] = None):
        self.config = config
        self._whitelist = self._normalize_whitelist(whitelist or {})

    def evaluate(self, request: ABExperimentRequest) -> ABExperimentResponse:
        assignments = {}
        hash_value = self._hash_uid(request.user_id)
        whitelist_rules = self._whitelist.get(request.user_id, {})
        selected_experiments = self._select_experiments(request.experiment_names)

        for experiment in selected_experiments:
            # 白名单优先：允许指定用户直达某策略，方便测试验证。
            forced_strategy_id = whitelist_rules.get(experiment.name)
            if forced_strategy_id:
                strategy = self._match_strategy_by_id(
                    forced_strategy_id, experiment.strategies,
                )
                if strategy is not None:
                    assignments[experiment.name] = ABExperimentAssignment(
                        experiment_name=experiment.name,
                        strategy_id=strategy.id,
                        params=dict(strategy.params),
                        hit_reason="whitelist",
                    )
                    continue
                logger.warning(
                    "ab_sdk whitelist invalid: user_id=%s experiment=%s strategy=%s",
                    request.user_id, experiment.name, forced_strategy_id,
                )

            strategy = self._match_strategy(hash_value, experiment.strategies)
            if strategy is not None:
                assignments[experiment.name] = ABExperimentAssignment(
                    experiment_name=experiment.name,
                    strategy_id=strategy.id,
                    params=dict(strategy.params),
                    hit_reason="hash",
                )
            else:
                logger.warning(
                    "ab_sdk miss strategy: user_id=%s hash=%d experiment=%s",
                    request.user_id, hash_value, experiment.name,
                )

        return ABExperimentResponse(
            request_id=request.request_id,
            user_id=request.user_id,
            assignments=assignments,
            trace_id=str(uuid.uuid4()),
        )

    def set_whitelist(self, whitelist: dict) -> None:
        """整量更新白名单。"""
        self._whitelist = self._normalize_whitelist(whitelist)

    def set_user_whitelist(self, user_id: str, strategy_map: dict) -> None:
        """更新单个用户白名单策略。"""
        normalized = self._normalize_user_whitelist(user_id, strategy_map)
        if normalized is None:
            return
        normalized_user_id, normalized_strategy_map = normalized
        self._whitelist[normalized_user_id] = normalized_strategy_map

    def clear_whitelist(self, user_id: Optional[str] = None) -> None:
        """清空全部白名单或指定用户白名单。"""
        if user_id is None:
            self._whitelist = {}
            return
        self._whitelist.pop(user_id, None)

    def get_whitelist(self) -> dict:
        """获取当前白名单快照。"""
        return {
            user_id: dict(strategy_map)
            for user_id, strategy_map in self._whitelist.items()
        }

    def _hash_uid(self, user_id: str) -> int:
        digest = hashlib.md5(user_id.encode()).hexdigest()
        return int(digest, 16) % 100

    def _match_strategy(
        self, hash_value: int, strategies: list
    ) -> Optional[ExperimentStrategy]:
        for strategy in strategies:
            low, high = strategy.hash_range
            if low <= hash_value < high:
                return strategy
        return None

    def _match_strategy_by_id(
        self, strategy_id: str, strategies: list
    ) -> Optional[ExperimentStrategy]:
        for strategy in strategies:
            if strategy.id == strategy_id:
                return strategy
        return None

    def _normalize_whitelist(self, whitelist: dict) -> dict:
        if not isinstance(whitelist, dict):
            return {}

        normalized = {}
        for user_id, strategy_map in whitelist.items():
            normalized_user = self._normalize_user_whitelist(user_id, strategy_map)
            if normalized_user is None:
                continue
            key, value = normalized_user
            normalized[key] = value
        return normalized

    def _normalize_user_whitelist(
        self, user_id: str, strategy_map: dict,
    ) -> Optional[tuple[str, dict]]:
        if not isinstance(user_id, str) or not isinstance(strategy_map, dict):
            return None
        normalized_strategy_map = {
            exp_name: strategy_id
            for exp_name, strategy_id in strategy_map.items()
            if isinstance(exp_name, str) and isinstance(strategy_id, str)
        }
        return user_id, normalized_strategy_map

    def _select_experiments(self, experiment_names: Optional[list[str]]) -> list:
        """
        按业务侧传入实验名选择需要评估的实验。

        - None: 沿用 SDK 默认行为，评估全部实验（向后兼容）
        - []: 不评估任何实验
        - [name...]: 只评估指定实验，保持传入顺序
        """
        if experiment_names is None:
            return list(self.config.experiments)
        if not experiment_names:
            return []

        index = {
            experiment.name: experiment
            for experiment in self.config.experiments
        }
        selected = []
        seen = set()
        for name in experiment_names:
            if not isinstance(name, str) or name in seen:
                continue
            seen.add(name)
            experiment = index.get(name)
            if experiment is None:
                logger.warning("ab_sdk unknown experiment: %s", name)
                continue
            selected.append(experiment)
        return selected
