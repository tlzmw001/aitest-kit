"""分数校准模块：支持线性/分段规则并可串联。"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_NUMERIC_JSON_FILE = re.compile(r"^\d+\.json$")
_MATCHABLE_FIELDS = {
    "item_id",
    "coupon_type",
    "device",
    "external",
    "gender",
    "age",
    "total_spend",
}


@dataclass
class CalibratedScore:
    """校准后的分数"""
    item_id: str
    original_score: float
    calibrated_score: float


class Calibrator:
    """
    分数校准器。

    校准规则由实验参数中的目录路径驱动，目录内选择“序号最大”的 json 文件：
    - linear 目录：规则 y = kx + b
    - piecewise 目录：按分数区间选择 k/b，再计算 y = kx + b
    """

    def __init__(self, base_dir: Optional[str] = None):
        # 默认以 coupon_system 目录作为相对路径基准。
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent

    def calibrate(
        self,
        scene_id: int,
        scores: list,
        calibration_params: Optional[dict] = None,
        request_context: Optional[dict] = None,
        item_context_by_id: Optional[dict] = None,
    ) -> list:
        """
        对打分结果进行校准。

        Args:
            scene_id: 场景ID（仅用于日志）
            scores: list of objects with item_id and score attributes
            calibration_params: 实验参数，包含 calibration_dir.linear/piecewise
            request_context: 请求和用户维度字段（device/external/gender/age/total_spend）
            item_context_by_id: item_id -> item 字段（item_id/coupon_type）

        Returns:
            list[CalibratedScore]
        """
        calibration_params = calibration_params or {}
        request_context = request_context or {}
        item_context_by_id = item_context_by_id or {}

        calibration_dir = calibration_params.get("calibration_dir", {})
        linear_rules = self._load_latest_rules(calibration_dir.get("linear"))
        piecewise_rules = self._load_latest_rules(calibration_dir.get("piecewise"))

        results = []
        for item_score in scores:
            item_id = str(item_score.item_id)
            original = float(item_score.score)
            match_fields = self._build_match_fields(
                item_id=item_id,
                request_context=request_context,
                item_context=item_context_by_id.get(item_id, {}),
            )

            calibrated = original
            piecewise_coeff = self._select_piecewise_coeff(
                piecewise_rules=piecewise_rules,
                score=calibrated,
                match_fields=match_fields,
            )
            if piecewise_coeff is not None:
                k, b = piecewise_coeff
                calibrated = k * calibrated + b

            linear_coeff = self._select_linear_coeff(
                linear_rules=linear_rules,
                match_fields=match_fields,
            )
            if linear_coeff is not None:
                k, b = linear_coeff
                calibrated = k * calibrated + b

            # 中间步骤不截断，最终只做一次 clamp。
            calibrated = self._clamp01(calibrated)
            results.append(CalibratedScore(
                item_id=item_id,
                original_score=original,
                calibrated_score=round(calibrated, 4),
            ))

        logger.info(
            "校准 scene_id=%d: linear_rules=%d piecewise_rules=%d items=%d",
            scene_id, len(linear_rules), len(piecewise_rules), len(results),
        )
        return results

    def _load_latest_rules(self, dir_path: Optional[str]) -> list:
        directory = self._resolve_path(dir_path)
        if directory is None or not directory.exists() or not directory.is_dir():
            return []

        candidates = []
        for file in directory.iterdir():
            if not file.is_file():
                continue
            if not _NUMERIC_JSON_FILE.match(file.name):
                continue
            candidates.append((int(file.stem), file))

        if not candidates:
            return []

        _, latest_file = max(candidates, key=lambda x: x[0])
        try:
            with open(latest_file) as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            logger.warning("校准文件读取失败，忽略: %s", latest_file)
            return []

        if not isinstance(raw, list):
            logger.warning("校准文件格式错误（非 list），忽略: %s", latest_file)
            return []
        return raw

    def _resolve_path(self, path_raw: Optional[str]) -> Optional[Path]:
        if not isinstance(path_raw, str) or not path_raw.strip():
            return None
        path = Path(path_raw)
        if path.is_absolute():
            return path
        return self.base_dir / path

    def _build_match_fields(
        self, item_id: str, request_context: dict, item_context: dict,
    ) -> dict:
        fields = {"item_id": item_id}
        if isinstance(item_context, dict) and "coupon_type" in item_context:
            fields["coupon_type"] = item_context.get("coupon_type")

        if isinstance(request_context, dict):
            for key in ("device", "external", "gender", "age", "total_spend"):
                if key in request_context:
                    fields[key] = request_context.get(key)
        return fields

    def _select_linear_coeff(self, linear_rules: list, match_fields: dict):
        for rule in linear_rules:
            if not self._conditions_match(rule.get("conditions"), match_fields):
                continue
            coeff = self._extract_kb(rule)
            if coeff is not None:
                return coeff
            return None
        return None

    def _select_piecewise_coeff(self, piecewise_rules: list, score: float, match_fields: dict):
        for rule in piecewise_rules:
            if not self._conditions_match(rule.get("conditions"), match_fields):
                continue
            segments = rule.get("segments")
            if not isinstance(segments, list) or not segments:
                return None
            return self._select_segment_coeff(segments, score)
        return None

    def _select_segment_coeff(self, segments: list, score: float):
        for idx, seg in enumerate(segments):
            if not isinstance(seg, dict):
                continue
            kb = self._extract_kb(seg)
            range_raw = seg.get("range")
            if kb is None or not isinstance(range_raw, list) or len(range_raw) != 2:
                continue

            left = self._to_number(range_raw[0])
            right = self._to_number(range_raw[1])
            if left is None or right is None or right < left:
                continue

            is_last = idx == len(segments) - 1
            in_range = (left <= score <= right) if is_last else (left <= score < right)
            if in_range:
                return kb
        return None

    def _conditions_match(self, conditions: object, match_fields: dict) -> bool:
        if not isinstance(conditions, dict) or not conditions:
            return False

        for key, expected in conditions.items():
            if key not in _MATCHABLE_FIELDS:
                return False
            if key not in match_fields:
                return False
            if not self._value_equals(match_fields[key], expected):
                return False
        return True

    def _extract_kb(self, rule: dict):
        if not isinstance(rule, dict):
            return None
        k = self._to_number(rule.get("k"))
        b = self._to_number(rule.get("b"))
        if k is None or b is None:
            return None
        return k, b

    def _value_equals(self, actual: object, expected: object) -> bool:
        if actual == expected:
            return True

        actual_bool = self._to_bool(actual)
        expected_bool = self._to_bool(expected)
        if actual_bool is not None and expected_bool is not None:
            return actual_bool == expected_bool

        actual_num = self._to_number(actual)
        expected_num = self._to_number(expected)
        if actual_num is not None and expected_num is not None:
            return actual_num == expected_num

        return str(actual) == str(expected)

    def _to_bool(self, value: object) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if value == 1:
                return True
            if value == 0:
                return False
            return None
        if not isinstance(value, str):
            return None
        lowered = value.strip().lower()
        if lowered in {"true", "1"}:
            return True
        if lowered in {"false", "0"}:
            return False
        return None

    def _to_number(self, value: object) -> Optional[float]:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if not isinstance(value, str):
            return None
        try:
            return float(value.strip())
        except ValueError:
            return None

    def _clamp01(self, score: float) -> float:
        return max(0.0, min(1.0, score))
