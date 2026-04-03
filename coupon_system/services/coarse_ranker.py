"""粗排模块 — 根据实验策略对候选 item 进行截断"""
from __future__ import annotations

import logging
import random

logger = logging.getLogger(__name__)


class CoarseRanker:
    """粗排：根据策略参数对候选物料进行排序和截断"""

    def rank(self, items: list, strategy_params: dict) -> list:
        """
        对候选 items 进行粗排截断。

        Args:
            items: 候选物料列表，每个 item 是 dict，包含 item_id, value 等字段
            strategy_params: 实验策略参数，包含 truncate_count 和 truncate_rule

        Returns:
            截断后的物料列表
        """
        truncate_count = strategy_params.get("truncate_count", len(items))
        truncate_rule = strategy_params.get("truncate_rule", "top_value")

        if truncate_count >= len(items):
            return items

        if truncate_rule == "top_value":
            sorted_items = sorted(items, key=lambda x: x.get("value", 0), reverse=True)
        elif truncate_rule == "top_min_spend":
            sorted_items = sorted(items, key=lambda x: x.get("min_spend", 0), reverse=True)
        elif truncate_rule == "random":
            sorted_items = list(items)
            random.shuffle(sorted_items)
        else:
            logger.warning("未知粗排规则: %s，使用 top_value", truncate_rule)
            sorted_items = sorted(items, key=lambda x: x.get("value", 0), reverse=True)

        result = sorted_items[:truncate_count]
        logger.info(
            "粗排: %d → %d items, rule=%s",
            len(items), len(result), truncate_rule,
        )
        return result
