"""
优惠券核心业务逻辑 — 场景路由 → 配置读取 → 特征获取 → 规则粗筛 → 模型精排 → 兜底/限流

完整链路：
1. 业务方通过 gRPC 调用 ClaimCoupon
2. 根据请求中的 scene 字段进行场景路由
3. 读取该场景的策略配置
4. 从 Redis 获取用户特征（画像、领取记录、库存）
5. 规则引擎粗筛（资格校验、库存检查、频次限制）
6. 模型精排（调推理服务预估发放价值 ROI）
7. 兜底策略（模型超时/不可用时的默认处理）
8. QPS 限流
"""
from __future__ import annotations

import time
import uuid

from coupon_system.config import AppConfig, SceneConfig, CouponTemplate
from coupon_system.services.redis_store import RedisStore
from coupon_system.services.model_service import MockModelService


class CouponError:
    """错误码定义"""
    OK = 0
    INVALID_PARAM = 1001
    SCENE_NOT_FOUND = 1002
    COUPON_NOT_FOUND = 1003
    SCENE_MISMATCH = 1004
    ALREADY_CLAIMED = 1005
    STOCK_EMPTY = 1006
    CLAIM_LIMIT_EXCEEDED = 1007
    NOT_NEW_USER = 1008
    NOT_MEMBER = 1009
    RATE_LIMITED = 1010
    MODEL_REJECTED = 1011
    INTERNAL_ERROR = 5000

    MESSAGES = {
        OK: "success",
        INVALID_PARAM: "参数无效",
        SCENE_NOT_FOUND: "场景不存在",
        COUPON_NOT_FOUND: "优惠券不存在",
        SCENE_MISMATCH: "优惠券不适用于当前场景",
        ALREADY_CLAIMED: "已经领取过该优惠券",
        STOCK_EMPTY: "库存不足",
        CLAIM_LIMIT_EXCEEDED: "超过领取次数限制",
        NOT_NEW_USER: "非新用户，不满足领取条件",
        NOT_MEMBER: "非会员，不满足领取条件",
        RATE_LIMITED: "请求过于频繁，请稍后重试",
        MODEL_REJECTED: "发放价值评估未通过",
        INTERNAL_ERROR: "内部错误",
    }


class CouponBizService:
    """优惠券核心业务服务"""

    def __init__(self, config: AppConfig, redis_store: RedisStore, model_service: MockModelService):
        self.config = config
        self.redis = redis_store
        self.model = model_service

    def claim_coupon(self, user_id: str, coupon_id: str, scene: str, extra: dict | None = None) -> dict:
        """
        领取优惠券 — 完整链路

        Returns:
            {"code": int, "message": str, "coupon": dict | None}
        """
        # 0. 参数校验
        if not user_id or not coupon_id or not scene:
            return self._error(CouponError.INVALID_PARAM)

        # 1. 限流检查
        if self.config.rate_limit.enabled:
            # 全局限流
            if not self.redis.check_rate_limit(
                "global", self.config.rate_limit.max_qps, self.config.rate_limit.window_seconds
            ):
                return self._error(CouponError.RATE_LIMITED)
            # 用户级限流
            if not self.redis.check_rate_limit(
                f"user:{user_id}", self.config.rate_limit.per_user_qps, self.config.rate_limit.window_seconds
            ):
                return self._error(CouponError.RATE_LIMITED)

        # 2. 场景路由
        scene_config = self.config.scenes.get(scene)
        if not scene_config:
            return self._error(CouponError.SCENE_NOT_FOUND)

        # 3. 读取优惠券模板配置
        template = self.config.coupon_templates.get(coupon_id)
        if not template:
            return self._error(CouponError.COUPON_NOT_FOUND)

        # 4. 场景匹配检查
        if scene not in template.scenes:
            return self._error(CouponError.SCENE_MISMATCH)

        # 5. 从 Redis 获取用户特征
        user_profile = self.redis.get_user_profile(user_id) or {}

        # 6. 规则引擎粗筛
        rule_result = self._rule_check(user_id, coupon_id, scene, scene_config, template, user_profile)
        if rule_result is not None:
            return rule_result

        # 7. 模型精排（评估发放价值）
        model_result = self._model_evaluate(user_id, coupon_id, scene, user_profile)
        if model_result is not None and model_result["code"] != CouponError.OK:
            return model_result

        # 8. 库存扣减（原子操作）
        remaining = self.redis.decr_stock(coupon_id)
        if remaining < 0:
            return self._error(CouponError.STOCK_EMPTY)

        # 9. 记录领取
        instance_id = str(uuid.uuid4())
        now = int(time.time())
        coupon_data = {
            "id": instance_id,
            "coupon_id": coupon_id,
            "user_id": user_id,
            "status": "claimed",
            "coupon_type": template.type,
            "value": template.value,
            "min_spend": template.min_spend,
            "expire_time": now + template.expire_days * 86400,
            "claim_time": now,
        }

        self.redis.record_claim(user_id, coupon_id, self.config.redis.user_claim_ttl)
        self.redis.incr_scene_claim_count(user_id, scene, self.config.redis.user_claim_ttl)
        self.redis.save_coupon_instance(instance_id, coupon_data, template.expire_days * 86400)
        self.redis.add_user_coupon(user_id, instance_id, template.expire_days * 86400)

        return {
            "code": CouponError.OK,
            "message": CouponError.MESSAGES[CouponError.OK],
            "coupon": coupon_data,
        }

    def query_user_coupons(
        self, user_id: str, status_filter: str = "all", page: int = 1, page_size: int = 20
    ) -> dict:
        """查询用户优惠券列表"""
        if not user_id:
            return {"code": CouponError.INVALID_PARAM, "message": "user_id不能为空", "coupons": [], "total": 0}

        instance_ids = self.redis.get_user_coupons(user_id)
        coupons = []
        for iid in instance_ids:
            data = self.redis.get_coupon_instance(iid)
            if data:
                if status_filter != "all" and data.get("status") != status_filter:
                    continue
                coupons.append(data)

        # 按领取时间倒序
        coupons.sort(key=lambda x: x.get("claim_time", 0), reverse=True)
        total = len(coupons)

        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        page_coupons = coupons[start:end]

        return {
            "code": CouponError.OK,
            "message": CouponError.MESSAGES[CouponError.OK],
            "coupons": page_coupons,
            "total": total,
        }

    def batch_evaluate(self, user_id: str, scene: str, candidate_coupon_ids: list[str]) -> dict:
        """批量评估优惠券发放价值"""
        if not user_id or not scene or not candidate_coupon_ids:
            return {"code": CouponError.INVALID_PARAM, "message": "参数不完整", "results": []}

        user_profile = self.redis.get_user_profile(user_id) or {}
        features = self._build_features(user_profile, scene)

        try:
            predictions = self.model.batch_predict(user_id, candidate_coupon_ids, features)
            results = []
            for cid, pred in zip(candidate_coupon_ids, predictions):
                results.append({
                    "coupon_id": cid,
                    "score": pred["score"],
                    "recommended": pred["recommended"],
                    "reason": pred["reason"],
                })
            return {
                "code": CouponError.OK,
                "message": CouponError.MESSAGES[CouponError.OK],
                "results": results,
            }
        except (TimeoutError, RuntimeError):
            # 兜底
            fallback_score = self.config.fallback.on_model_unavailable.default_score
            results = [
                {
                    "coupon_id": cid,
                    "score": fallback_score,
                    "recommended": fallback_score >= 0.5,
                    "reason": "模型服务不可用，使用兜底分数",
                }
                for cid in candidate_coupon_ids
            ]
            return {
                "code": CouponError.OK,
                "message": "使用兜底策略",
                "results": results,
            }

    # ========== 内部方法 ==========

    def _rule_check(
        self,
        user_id: str,
        coupon_id: str,
        scene: str,
        scene_config: SceneConfig,
        template: CouponTemplate,
        user_profile: dict,
    ) -> dict | None:
        """规则引擎粗筛，返回 None 表示通过"""
        # 新用户检查
        if scene_config.require_new_user and not user_profile.get("is_new_user", False):
            return self._error(CouponError.NOT_NEW_USER)

        # 会员检查
        if scene_config.require_member and not user_profile.get("is_member", False):
            return self._error(CouponError.NOT_MEMBER)

        # 重复领取检查
        if self.redis.has_claimed(user_id, coupon_id):
            return self._error(CouponError.ALREADY_CLAIMED)

        # 场景领取次数限制
        claim_count = self.redis.get_user_claim_count(user_id, scene)
        if claim_count >= scene_config.max_claim_per_user:
            return self._error(CouponError.CLAIM_LIMIT_EXCEEDED)

        # 库存检查（预检，正式扣减在后续步骤）
        stock = self.redis.get_stock(coupon_id)
        if stock <= 0:
            return self._error(CouponError.STOCK_EMPTY)

        return None  # 通过

    def _model_evaluate(self, user_id: str, coupon_id: str, scene: str, user_profile: dict) -> dict | None:
        """模型精排 + 兜底"""
        if not self.model.enabled:
            return None  # 模型关闭，跳过

        features = self._build_features(user_profile, scene)

        try:
            result = self.model.predict(user_id, coupon_id, features)
            if not result["recommended"]:
                return self._error(CouponError.MODEL_REJECTED)
            return {"code": CouponError.OK, "message": "模型评估通过"}

        except TimeoutError:
            if self.config.fallback.enabled:
                action = self.config.fallback.on_model_timeout.action
                if action == "allow":
                    return None  # 放行
                elif action == "deny":
                    return self._error(CouponError.MODEL_REJECTED)
            return self._error(CouponError.INTERNAL_ERROR)

        except RuntimeError:
            if self.config.fallback.enabled:
                action = self.config.fallback.on_model_unavailable.action
                if action == "allow":
                    return None  # 放行
                elif action == "deny":
                    return self._error(CouponError.MODEL_REJECTED)
            return self._error(CouponError.INTERNAL_ERROR)

    def _build_features(self, user_profile: dict, scene: str) -> dict:
        """构建特征字典"""
        return {
            "is_new_user": user_profile.get("is_new_user", False),
            "is_member": user_profile.get("is_member", False),
            "total_spend": user_profile.get("total_spend", 0),
            "register_days": user_profile.get("register_days", 0),
            "scene": scene,
        }

    def _error(self, code: int) -> dict:
        return {
            "code": code,
            "message": CouponError.MESSAGES.get(code, "未知错误"),
            "coupon": None,
        }
