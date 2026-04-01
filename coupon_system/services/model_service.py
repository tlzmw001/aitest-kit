"""Mock 推理服务 — 模拟模型精排，返回优惠券发放价值分数"""
from __future__ import annotations

import random
import time


class MockModelService:
    """模拟推理服务，用于评估优惠券发放的 ROI 价值"""

    def __init__(self, timeout: float = 2.0, enabled: bool = True):
        self.timeout = timeout
        self.enabled = enabled
        self._simulate_failure = False
        self._simulate_timeout = False

    def predict(self, user_id: str, coupon_id: str, features: dict) -> dict:
        """
        预估优惠券发放价值。

        Args:
            user_id: 用户ID
            coupon_id: 优惠券ID
            features: 用户+券特征

        Returns:
            {"score": float, "recommended": bool, "reason": str}

        Raises:
            TimeoutError: 模拟超时
            RuntimeError: 模拟服务不可用
        """
        if not self.enabled:
            raise RuntimeError("Model service is disabled")

        if self._simulate_failure:
            raise RuntimeError("Model service unavailable")

        if self._simulate_timeout:
            time.sleep(self.timeout + 1)
            raise TimeoutError("Model service timeout")

        # Mock 评分逻辑
        score = self._calculate_score(user_id, coupon_id, features)
        recommended = score >= 0.5

        reasons = {
            True: "用户匹配度高，预估ROI正向",
            False: "用户匹配度低，预估ROI不足",
        }

        return {
            "score": round(score, 4),
            "recommended": recommended,
            "reason": reasons[recommended],
        }

    def batch_predict(
        self, user_id: str, coupon_ids: list[str], features: dict
    ) -> list[dict]:
        """批量预估"""
        return [
            self.predict(user_id, cid, features) for cid in coupon_ids
        ]

    def _calculate_score(self, user_id: str, coupon_id: str, features: dict) -> float:
        """Mock 评分：基于简单规则 + 随机因子"""
        base_score = 0.5

        # 新用户加分
        if features.get("is_new_user"):
            base_score += 0.2

        # 会员加分
        if features.get("is_member"):
            base_score += 0.1

        # 历史消费越高加分越多
        spend = features.get("total_spend", 0)
        if spend > 10000:
            base_score += 0.1
        elif spend > 5000:
            base_score += 0.05

        # 随机因子（模拟模型不确定性）
        noise = random.uniform(-0.1, 0.1)
        score = max(0.0, min(1.0, base_score + noise))

        return score

    # ========== 测试辅助方法 ==========

    def set_simulate_failure(self, enabled: bool) -> None:
        """设置是否模拟服务故障"""
        self._simulate_failure = enabled

    def set_simulate_timeout(self, enabled: bool) -> None:
        """设置是否模拟超时"""
        self._simulate_timeout = enabled
