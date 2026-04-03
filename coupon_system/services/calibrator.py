"""分数校准模块 — y = k * x + b"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from coupon_system.config import CalibrationCoefficients

logger = logging.getLogger(__name__)


@dataclass
class CalibratedScore:
    """校准后的分数"""
    item_id: str
    original_score: float
    calibrated_score: float


class Calibrator:
    """分数校准器：根据场景的 k/b 系数对打分结果进行校准"""

    def __init__(self, coefficients: dict):
        """
        Args:
            coefficients: dict[str, CalibrationCoefficients]
                          key 为 scene_id 字符串，value 为 CalibrationCoefficients
        """
        self.coefficients = coefficients

    def calibrate(self, scene_id: int, scores: list) -> list:
        """
        对打分结果进行校准。

        Args:
            scene_id: 场景ID
            scores: list of objects with item_id and score attributes

        Returns:
            list[CalibratedScore]
        """
        coeff = self.coefficients.get(str(scene_id))
        if coeff is None:
            coeff = self.coefficients.get("default", CalibrationCoefficients())

        results = []
        for item_score in scores:
            calibrated = coeff.k * item_score.score + coeff.b
            calibrated = max(0.0, min(1.0, calibrated))

            results.append(CalibratedScore(
                item_id=item_score.item_id,
                original_score=item_score.score,
                calibrated_score=round(calibrated, 4),
            ))

        logger.info(
            "校准 scene_id=%d: k=%.2f, b=%.2f, %d items",
            scene_id, coeff.k, coeff.b, len(results),
        )
        return results
