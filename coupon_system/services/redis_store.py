"""Redis 数据层 — 库存管理、领取记录、用户画像"""
from __future__ import annotations

import json
import time
from typing import Optional

import redis


class RedisStore:
    """优惠券系统的 Redis 数据操作"""

    def __init__(self, redis_url: str, key_prefix: str = "coupon:"):
        self.client = redis.from_url(redis_url, decode_responses=True)
        self.prefix = key_prefix

    def _key(self, *parts: str) -> str:
        return self.prefix + ":".join(parts)

    # ========== 库存 ==========

    def init_stock(self, coupon_id: str, stock: int, ttl: int = 86400) -> None:
        """初始化库存"""
        key = self._key("stock", coupon_id)
        self.client.set(key, stock, ex=ttl)

    def get_stock(self, coupon_id: str) -> int:
        """获取当前库存"""
        val = self.client.get(self._key("stock", coupon_id))
        return int(val) if val is not None else 0

    def decr_stock(self, coupon_id: str) -> int:
        """扣减库存，返回扣减后的值。如果 <0 说明库存不足，需要回滚。"""
        key = self._key("stock", coupon_id)
        result = self.client.decr(key)
        if result < 0:
            # 回滚
            self.client.incr(key)
            return -1
        return result

    # ========== 用户领取记录 ==========

    def has_claimed(self, user_id: str, coupon_id: str) -> bool:
        """检查用户是否已领取某券"""
        key = self._key("user", user_id, "claimed")
        return self.client.sismember(key, coupon_id)

    def record_claim(self, user_id: str, coupon_id: str, ttl: int = 604800) -> None:
        """记录用户领取"""
        key = self._key("user", user_id, "claimed")
        self.client.sadd(key, coupon_id)
        self.client.expire(key, ttl)

    def get_user_claim_count(self, user_id: str, scene: str) -> int:
        """获取用户在某场景下的领取次数"""
        key = self._key("user", user_id, "scene_count", scene)
        val = self.client.get(key)
        return int(val) if val is not None else 0

    def incr_scene_claim_count(self, user_id: str, scene: str, ttl: int = 604800) -> int:
        """增加用户在某场景下的领取计数"""
        key = self._key("user", user_id, "scene_count", scene)
        result = self.client.incr(key)
        self.client.expire(key, ttl)
        return result

    # ========== 用户画像（兼容旧接口） ==========

    def get_user_profile(self, user_id: str) -> Optional[dict]:
        """获取用户画像（整体 JSON，兼容 admin 接口）"""
        key = self._key("user_profile", user_id)
        data = self.client.get(key)
        return json.loads(data) if data else None

    def set_user_profile(self, user_id: str, profile: dict, ttl: int = 86400) -> None:
        """设置用户画像（整体 JSON，兼容 admin 接口）"""
        key = self._key("user_profile", user_id)
        self.client.set(key, json.dumps(profile), ex=ttl)

    # ========== 用户特征（按字段） ==========

    def get_user_feature(self, user_id: str, feature_name: str) -> Optional[str]:
        """获取单个用户特征，key: {prefix}user_feature:{feature_name}:{uid}"""
        key = self._key("user_feature", feature_name, user_id)
        return self.client.get(key)

    def set_user_feature(
        self, user_id: str, feature_name: str, value: str, ttl: int = 86400
    ) -> None:
        """设置单个用户特征"""
        key = self._key("user_feature", feature_name, user_id)
        self.client.set(key, value, ex=ttl)

    def set_user_features(self, user_id: str, features: dict, ttl: int = 86400) -> None:
        """批量设置用户特征"""
        pipe = self.client.pipeline()
        for feature_name, value in features.items():
            key = self._key("user_feature", feature_name, user_id)
            pipe.set(key, str(value), ex=ttl)
        pipe.execute()

    # ========== 限流 ==========

    def check_rate_limit(self, key_suffix: str, max_count: int, window: int = 1) -> bool:
        """滑动窗口限流，返回 True 表示未触发限流"""
        key = self._key("rate", key_suffix)
        now = time.time()
        pipe = self.client.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window + 1)
        results = pipe.execute()
        current_count = results[2]
        return current_count <= max_count

    # ========== 优惠券实例存储 ==========

    def save_coupon_instance(self, instance_id: str, data: dict, ttl: int = 604800) -> None:
        """保存优惠券实例"""
        key = self._key("instance", instance_id)
        self.client.set(key, json.dumps(data), ex=ttl)

    def get_coupon_instance(self, instance_id: str) -> Optional[dict]:
        """获取优惠券实例"""
        key = self._key("instance", instance_id)
        data = self.client.get(key)
        return json.loads(data) if data else None

    def get_user_coupons(self, user_id: str) -> list[str]:
        """获取用户所有优惠券实例ID"""
        key = self._key("user", user_id, "instances")
        return list(self.client.smembers(key))

    def add_user_coupon(self, user_id: str, instance_id: str, ttl: int = 604800) -> None:
        """将优惠券实例关联到用户"""
        key = self._key("user", user_id, "instances")
        self.client.sadd(key, instance_id)
        self.client.expire(key, ttl)

    # ========== 兜底分 ==========

    def get_fallback_score(self, scene_id: Optional[int] = None) -> Optional[float]:
        """
        获取兜底分。
        优先读取 scene 级别：fallback:score:{scene_id}
        其次读取全局默认：fallback:score:default
        """
        if scene_id is not None:
            scene_val = self.client.get(self._key("fallback", "score", str(scene_id)))
            if scene_val is not None:
                try:
                    return float(scene_val)
                except ValueError:
                    return None

        default_val = self.client.get(self._key("fallback", "score", "default"))
        if default_val is None:
            return None

        try:
            return float(default_val)
        except ValueError:
            return None

    def set_fallback_score(
        self, score: float, scene_id: Optional[int] = None, ttl: int = 86400,
    ) -> None:
        """设置兜底分（测试/运维辅助）"""
        if scene_id is None:
            key = self._key("fallback", "score", "default")
        else:
            key = self._key("fallback", "score", str(scene_id))
        self.client.set(key, str(score), ex=ttl)
