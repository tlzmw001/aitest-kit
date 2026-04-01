"""Redis 数据层 — 库存管理、领取记录、用户画像"""
from __future__ import annotations

import json
import time

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

    # ========== 用户画像 ==========

    def get_user_profile(self, user_id: str) -> dict | None:
        """获取用户画像"""
        key = self._key("user_profile", user_id)
        data = self.client.get(key)
        return json.loads(data) if data else None

    def set_user_profile(self, user_id: str, profile: dict, ttl: int = 86400) -> None:
        """设置用户画像"""
        key = self._key("user_profile", user_id)
        self.client.set(key, json.dumps(profile), ex=ttl)

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

    def get_coupon_instance(self, instance_id: str) -> dict | None:
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
