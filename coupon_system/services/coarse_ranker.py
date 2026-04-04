"""粗排模块 — 根据实验策略对候选 item 进行截断"""
from __future__ import annotations

import logging
import random
from collections import defaultdict
from typing import Optional

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
        if not items:
            return []

        truncate_count = self._as_int(strategy_params.get("truncate_count", len(items)), len(items))
        truncate_count = max(0, truncate_count)
        if truncate_count == 0:
            return []

        prior_count = strategy_params.get("prior_count", None)
        filters = strategy_params.get("filters", None)
        sort_keys = strategy_params.get("sort_keys", None)
        diversity = strategy_params.get("diversity", None)

        # 向后兼容：如果未开启任何新能力且无需截断，直接返回原顺序。
        if (
            prior_count is None
            and not filters
            and not sort_keys
            and not diversity
            and truncate_count >= len(items)
        ):
            return list(items)

        # 阶段0：保送
        selected_prior, remaining = self._prior_select(items, strategy_params, truncate_count)

        # 阶段1：过滤
        filtered = self._apply_filters(remaining, strategy_params)

        # 阶段2：排序（多维排序或旧规则）
        ranked = self._sort_candidates(filtered, strategy_params)

        # 阶段3：打散 + 截断
        target_count = max(truncate_count - len(selected_prior), 0)
        selected_main = self._truncate_with_diversity(ranked, strategy_params, target_count)

        result = selected_prior + selected_main
        logger.info(
            "粗排: %d → %d items, truncate_count=%d",
            len(items), len(result), truncate_count,
        )
        return result

    def _prior_select(self, items: list, strategy_params: dict, truncate_count: int) -> tuple[list, list]:
        prior_count = strategy_params.get("prior_count", None)
        if prior_count is None:
            return [], list(items)

        prior_count = self._as_int(prior_count, 0)
        prior_count = max(0, prior_count)
        if prior_count > truncate_count:
            logger.warning(
                "prior_count=%d 大于 truncate_count=%d，已截断到 truncate_count",
                prior_count, truncate_count,
            )
            prior_count = truncate_count
        if prior_count == 0:
            return [], list(items)

        prior_rule = strategy_params.get("prior_rule", "top_value")
        indexed_items = list(enumerate(items))
        prior_candidates = [(idx, item) for idx, item in indexed_items if self._is_prior(item)]

        if prior_rule == "top_value":
            prior_candidates.sort(key=lambda p: self._as_float(p[1].get("value", 0), 0.0), reverse=True)
        elif prior_rule == "random":
            random.shuffle(prior_candidates)
        else:
            logger.warning("未知 prior_rule: %s，使用 top_value", prior_rule)
            prior_candidates.sort(key=lambda p: self._as_float(p[1].get("value", 0), 0.0), reverse=True)

        selected_pairs = prior_candidates[:prior_count]
        selected_indices = {idx for idx, _ in selected_pairs}
        # 保送结果应保持 prior_rule 产生的顺序，而不是原始输入顺序。
        selected_prior = [item for _, item in selected_pairs]
        remaining = [item for idx, item in indexed_items if idx not in selected_indices]
        return selected_prior, remaining

    def _apply_filters(self, items: list, strategy_params: dict) -> list:
        filters = strategy_params.get("filters", [])
        if not filters:
            return list(items)

        result = []
        for item in items:
            if self._match_all_filters(item, filters):
                result.append(item)
        return result

    def _match_all_filters(self, item: dict, filters: list) -> bool:
        for cond in filters:
            if not isinstance(cond, dict):
                return False
            field = cond.get("field")
            op = cond.get("op")
            expected = cond.get("value")
            actual = item.get(field)

            if not self._match_filter(actual, op, expected):
                return False
        return True

    def _match_filter(self, actual, op: str, expected) -> bool:
        if op == "eq":
            return actual == expected
        if op == "neq":
            return actual != expected

        if op in {"gt", "gte", "lt", "lte"}:
            actual_num = self._as_float(actual, None)
            expected_num = self._as_float(expected, None)
            if actual_num is None or expected_num is None:
                return False
            if op == "gt":
                return actual_num > expected_num
            if op == "gte":
                return actual_num >= expected_num
            if op == "lt":
                return actual_num < expected_num
            return actual_num <= expected_num

        if op == "in":
            return actual in expected if isinstance(expected, list) else False
        if op == "not_in":
            return actual not in expected if isinstance(expected, list) else False

        logger.warning("未知过滤操作符: %s", op)
        return False

    def _sort_candidates(self, items: list, strategy_params: dict) -> list:
        if not items:
            return []

        sort_keys = strategy_params.get("sort_keys", [])
        if sort_keys:
            return self._sort_by_weighted_score(items, sort_keys)

        return self._sort_by_legacy_rule(items, strategy_params.get("truncate_rule", "top_value"))

    def _sort_by_weighted_score(self, items: list, sort_keys: list) -> list:
        ranges = {}
        for key in sort_keys:
            if not isinstance(key, dict):
                continue
            field = key.get("field")
            if not isinstance(field, str):
                continue
            values = [
                self._as_float(item.get(field), 0.0)
                for item in items
            ]
            ranges[field] = (min(values), max(values))

        scored = []
        for index, item in enumerate(items):
            score = 0.0
            for key in sort_keys:
                if not isinstance(key, dict):
                    continue
                field = key.get("field")
                if not isinstance(field, str):
                    continue
                weight = self._as_float(key.get("weight"), 0.0)
                low, high = ranges.get(field, (0.0, 0.0))
                val = self._as_float(item.get(field), 0.0)
                normalized = 0.0 if high == low else (val - low) / (high - low)
                score += normalized * weight
            scored.append((index, score, item))

        scored.sort(key=lambda x: (x[1], -x[0]), reverse=True)
        return [item for _, _, item in scored]

    def _sort_by_legacy_rule(self, items: list, truncate_rule: str) -> list:
        if truncate_rule == "top_value":
            return sorted(items, key=lambda x: self._as_float(x.get("value", 0), 0.0), reverse=True)
        if truncate_rule == "top_min_spend":
            return sorted(items, key=lambda x: self._as_float(x.get("min_spend", 0), 0.0), reverse=True)
        if truncate_rule == "random":
            shuffled = list(items)
            random.shuffle(shuffled)
            return shuffled

        logger.warning("未知粗排规则: %s，使用 top_value", truncate_rule)
        return sorted(items, key=lambda x: self._as_float(x.get("value", 0), 0.0), reverse=True)

    def _truncate_with_diversity(self, ranked_items: list, strategy_params: dict, target_count: int) -> list:
        if target_count <= 0 or not ranked_items:
            return []

        diversity = strategy_params.get("diversity", {})
        if not isinstance(diversity, dict) or not diversity.get("enabled"):
            return ranked_items[:target_count]

        group_field = diversity.get("group_field")
        max_per_group = self._as_int(diversity.get("max_per_group", 0), 0)
        if not isinstance(group_field, str) or max_per_group <= 0:
            return ranked_items[:target_count]

        selected = []
        backfill = []
        group_count = defaultdict(int)
        for item in ranked_items:
            group_key = item.get(group_field)
            if group_count[group_key] < max_per_group:
                selected.append(item)
                group_count[group_key] += 1
                if len(selected) >= target_count:
                    break
            else:
                backfill.append(item)

        if len(selected) < target_count:
            for item in backfill:
                selected.append(item)
                if len(selected) >= target_count:
                    break
        return selected

    def _is_prior(self, item: dict) -> bool:
        value = item.get("isPrior", False)
        if isinstance(value, str):
            return value.lower() == "true"
        return bool(value)

    def _as_float(self, value, default: Optional[float]) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _as_int(self, value, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
