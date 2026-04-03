"""特征抽取模块 — 用户特征从 Redis，item 特征从文件"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from coupon_system.services.redis_store import RedisStore

logger = logging.getLogger(__name__)


class FeatureStore:
    """特征仓库：管理用户特征和 item 特征的读取"""

    def __init__(
        self,
        redis_store: RedisStore,
        user_feature_keys: list,
        item_feature_file: str,
    ):
        self.redis = redis_store
        self.user_feature_keys = user_feature_keys
        self._item_features = {}
        self._load_item_features(item_feature_file)

    def _load_item_features(self, file_path: str) -> None:
        """加载 item 特征文件（TSV 格式：item_id\\tJSON）"""
        path = Path(file_path)
        if not path.is_absolute():
            # 相对于 coupon_system/ 目录
            path = Path(__file__).parent.parent / file_path

        if not path.exists():
            logger.warning("item 特征文件不存在: %s", path)
            return

        count = 0
        with open(path) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t", 1)
                if len(parts) != 2:
                    logger.warning("item 特征文件第 %d 行格式错误，跳过", line_num)
                    continue
                item_id, features_json = parts
                try:
                    self._item_features[item_id] = json.loads(features_json)
                    count += 1
                except json.JSONDecodeError:
                    logger.warning("item 特征文件第 %d 行 JSON 解析失败，跳过", line_num)

        logger.info("加载 item 特征: %d 条", count)

    def get_user_features(self, user_id: str) -> dict:
        """
        从 Redis 读取用户特征。
        key 格式: {prefix}user_feature:{feature_name}:{uid}

        Returns:
            dict: {feature_name: feature_value}
        """
        features = {}
        for feature_name in self.user_feature_keys:
            value = self.redis.get_user_feature(user_id, feature_name)
            if value is not None:
                features[feature_name] = value
        return features

    def get_item_features(self, item_id: str) -> dict:
        """获取 item 特征（从内存缓存读取）"""
        return dict(self._item_features.get(item_id, {}))

    def reload_item_features(self, file_path: str) -> None:
        """重新加载 item 特征文件"""
        self._item_features.clear()
        self._load_item_features(file_path)
