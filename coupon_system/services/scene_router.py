"""场景路由模块 — 根据 sceneName + device + policyId 确定 sceneId"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from coupon_system.config import SceneRoutingConfig

logger = logging.getLogger(__name__)


@dataclass
class SceneResult:
    """场景路由结果"""
    scene_id: int
    is_fallback: bool = False
    fallback_score: float = 0.5


class SceneRouter:
    """场景路由器"""

    def __init__(self, config: SceneRoutingConfig):
        self.config = config
        # 构建查找表: (scene_name, device) -> scene_id
        self._route_map = {}
        for route in config.routes:
            key = (route.scene_name, route.device)
            self._route_map[key] = route.scene_id

    def route(self, scene_name: str, device: str, policy_id: str) -> SceneResult:
        """
        路由到具体场景。

        Args:
            scene_name: 场景名 (game, ad)
            device: 设备类型 (mobile, pc, pad)
            policy_id: 策略ID，命中则走兜底

        Returns:
            SceneResult: 包含 scene_id 和是否兜底
        """
        # 先检查 policyId 是否命中兜底
        if policy_id and policy_id in self.config.fallback_policy_ids:
            logger.info(
                "policy_id=%s 命中兜底，scene_id=%d",
                policy_id, self.config.fallback_scene_id,
            )
            return SceneResult(
                scene_id=self.config.fallback_scene_id,
                is_fallback=True,
                fallback_score=self.config.fallback_score,
            )

        # 按 scene_name + device 查找
        key = (scene_name, device)
        scene_id = self._route_map.get(key)
        if scene_id is None:
            logger.warning(
                "未匹配场景: scene_name=%s, device=%s，使用兜底",
                scene_name, device,
            )
            return SceneResult(
                scene_id=self.config.fallback_scene_id,
                is_fallback=True,
                fallback_score=self.config.fallback_score,
            )

        return SceneResult(scene_id=scene_id)
