"""
优惠券策略核心业务逻辑 — 推荐 + 发放 pipeline

完整链路：
1. 参数校验
2. 限流（全局 + 用户级）
3. 场景路由（sceneName + device + policyId → sceneId）
4. AB 实验分流（按 scene_id 映射实验后再分流）
5. 粗排（实验控制，截断候选 items）
6. 特征抽取（用户 Redis + item 文件 + 上下文请求）
7. 调打分服务（独立 gRPC）
8. 校准（实验控制，y = kx + b）
9. 发放（库存扣减 + 记录领取）
10. 返回结果
"""
from __future__ import annotations

import enum
import logging
import time
import uuid
from typing import Optional

from ab_experiment_sdk import ABExperimentRequest, ABExperimentSDK
from coupon_system.config import AppConfig
from coupon_system.services.calibrator import Calibrator
from coupon_system.services.coarse_ranker import CoarseRanker
from coupon_system.services.feature_store import FeatureStore
from coupon_system.services.redis_store import RedisStore
from coupon_system.services.scene_router import SceneRouter
from coupon_system.services.scoring_client import ScoringClient

logger = logging.getLogger(__name__)


class _ScoringFailure(enum.Enum):
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"


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
    SCORING_ERROR = 1012
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
        SCORING_ERROR: "打分服务异常",
        INTERNAL_ERROR: "内部错误",
    }


class CouponBizService:
    """优惠券策略核心业务服务"""

    def __init__(
        self,
        config: AppConfig,
        redis_store: RedisStore,
        experiment_sdk: ABExperimentSDK,
        scene_experiment_mapping: dict,
        default_scene_experiments: list,
        scene_router: SceneRouter,
        coarse_ranker: CoarseRanker,
        feature_store: FeatureStore,
        scoring_client: ScoringClient,
        calibrator: Calibrator,
    ):
        self.config = config
        self.redis = redis_store
        self.experiment_sdk = experiment_sdk
        self.scene_experiment_mapping = dict(scene_experiment_mapping)
        self.default_scene_experiments = list(default_scene_experiments)
        self.scene_router = scene_router
        self.coarse_ranker = coarse_ranker
        self.feature_store = feature_store
        self.scoring_client = scoring_client
        self.calibrator = calibrator

    def recommend_and_claim(
        self,
        user_id: str,
        scene_name: str,
        device: str,
        policy_id: str,
        context: dict,
        items: list,
        external: Optional[int] = None,
        req_id: str = "",
        score_threshold: Optional[float] = None,
        max_claim_per_request: Optional[int] = None,
    ) -> dict:
        """
        推荐 + 发放 pipeline。

        Args:
            user_id: 用户ID
            scene_name: 场景名 (game, ad)
            device: 设备类型 (mobile, pc, pad)
            policy_id: 策略ID，命中配置则走兜底
            context: 上下文特征 {key: value}
            items: 候选券物料 [{item_id, coupon_type, value, min_spend, expire_days}]
            external: 打分路由（必传），0=内部服务，1=外部服务
            req_id: 业务侧传入的请求标识（用于日志排查）
            score_threshold: 分数阈值（必传）
            max_claim_per_request: 单次最多发放数量（必传）

        Returns:
            {code, message, scene_id, experiment_info, results, coupon}
        """
        # 0. 参数校验
        if not user_id or not scene_name or not device or not items:
            return self._error(CouponError.INVALID_PARAM)
        claim_controls = self._resolve_claim_controls(
            external=external,
            score_threshold=score_threshold,
            max_claim_per_request=max_claim_per_request,
        )
        if claim_controls is None:
            return self._error(CouponError.INVALID_PARAM)
        resolved_score_threshold, resolved_max_claim = claim_controls
        route = 2 if external == 1 else 1
        request_id = req_id or str(uuid.uuid4())

        # 1. 限流
        if self.config.rate_limit.enabled:
            if not self.redis.check_rate_limit(
                "global", self.config.rate_limit.max_qps,
                self.config.rate_limit.window_seconds,
            ):
                return self._error(CouponError.RATE_LIMITED)
            if not self.redis.check_rate_limit(
                f"user:{user_id}", self.config.rate_limit.per_user_qps,
                self.config.rate_limit.window_seconds,
            ):
                return self._error(CouponError.RATE_LIMITED)

        # 2. 场景路由
        scene = self.scene_router.route(scene_name, device, policy_id)
        item_ids = [str(item.get("item_id", "")) for item in items]
        logger.info(
            "recommend request: reqId=%s user_id=%s item_ids=%s route=%d scene_id=%d",
            request_id, user_id, ",".join(item_ids), route, scene.scene_id,
        )

        # 兜底场景：直接返回兜底分，不请求实验、不打分
        if scene.is_fallback:
            fallback_score = self._resolve_fallback_score(scene.scene_id, scene.fallback_score)
            return self._build_fallback_response(
                user_id=user_id,
                items=items,
                scene_id=scene.scene_id,
                fallback_score=fallback_score,
                experiment_info={},
                score_threshold=resolved_score_threshold,
                max_claim_per_request=resolved_max_claim,
            )

        # 3. AB 实验分流（先确定 scene_id，再按场景读取实验）
        exp_result = {}
        if route != 2:
            scene_experiments = self.scene_experiment_mapping.get(
                scene.scene_id, self.default_scene_experiments,
            )
            exp_result = self.experiment_sdk.evaluate(
                ABExperimentRequest(
                    user_id=user_id,
                    request_id=request_id,
                    context={
                        "scene_name": scene_name,
                        "device": device,
                        "policy_id": policy_id,
                        "scene_id": scene.scene_id,
                    },
                    experiment_names=scene_experiments,
                )
            ).assignments
        else:
            logger.info(
                "skip experiments for external scoring: reqId=%s scene_id=%d",
                request_id, scene.scene_id,
            )
        experiment_info = {
            name: result.strategy_id for name, result in exp_result.items()
        }

        # 4. 粗排（实验控制）
        working_items = [dict(item) for item in items]
        cr_exp = self._find_experiment_by_param(exp_result, "enable_coarse_rank")
        if cr_exp and cr_exp.params.get("enable_coarse_rank"):
            working_items = self.coarse_ranker.rank(working_items, cr_exp.params)

        # 5. 特征抽取
        user_features = self.feature_store.get_user_features(user_id)
        scoring_items = []
        for item in working_items:
            item_features = self.feature_store.get_item_features(item["item_id"])
            # 合并 item 请求字段和文件特征
            merged_features = {**item_features}
            for k in ("coupon_type", "value", "min_spend", "expire_days"):
                if k in item:
                    merged_features[k] = item[k]
            scoring_items.append({
                "item_id": item["item_id"],
                "features": merged_features,
            })

        # 6. 调打分服务
        scores = self._call_scoring(
            user_id=user_id,
            scene_id=scene.scene_id,
            user_features=user_features,
            context=context,
            items=scoring_items,
            external=external,
            req_id=request_id,
        )
        if isinstance(scores, _ScoringFailure):
            fallback = self.config.fallback
            if not fallback.enabled:
                return self._error(CouponError.SCORING_ERROR)
            if scores == _ScoringFailure.TIMEOUT:
                fallback_action = fallback.on_scoring_timeout
            else:
                fallback_action = fallback.on_scoring_unavailable
            if fallback_action.action != "allow":
                return self._error(CouponError.SCORING_ERROR)
            fallback_score = self._resolve_fallback_score(
                scene.scene_id, fallback_action.default_score,
            )
            return self._build_fallback_response(
                user_id=user_id,
                items=items,
                scene_id=scene.scene_id,
                fallback_score=fallback_score,
                experiment_info=experiment_info,
                score_threshold=resolved_score_threshold,
                max_claim_per_request=resolved_max_claim,
            )

        # 7. 校准（实验控制）
        cal_exp = self._find_experiment_by_param(exp_result, "enable_calibration")
        if cal_exp and cal_exp.params.get("enable_calibration"):
            calibration_request_context = {
                "device": device,
                "external": external,
                "gender": user_features.get("gender"),
                "age": user_features.get("age"),
                "total_spend": user_features.get("total_spend"),
            }
            item_context_by_id = {
                str(item.get("item_id")): item
                for item in working_items
                if item.get("item_id") is not None
            }
            calibrated = self.calibrator.calibrate(
                scene_id=scene.scene_id,
                scores=scores,
                calibration_params=cal_exp.params,
                request_context=calibration_request_context,
                item_context_by_id=item_context_by_id,
            )
            results = [
                {
                    "item_id": cs.item_id,
                    "score": cs.original_score,
                    "calibrated_score": cs.calibrated_score,
                    "recommended": cs.calibrated_score >= resolved_score_threshold,
                }
                for cs in calibrated
            ]
        else:
            results = [
                {
                    "item_id": s.item_id,
                    "score": s.score,
                    "calibrated_score": s.score,
                    "recommended": s.score >= resolved_score_threshold,
                }
                for s in scores
            ]

        # 8. 发放最优券
        coupon = self._do_claim(user_id, results, items, resolved_max_claim)

        return {
            "code": CouponError.OK,
            "message": CouponError.MESSAGES[CouponError.OK],
            "scene_id": scene.scene_id,
            "experiment_info": experiment_info,
            "results": results,
            "coupon": coupon,
        }

    def _find_experiment_by_param(self, exp_result: dict, param_name: str):
        """在命中的实验结果中，查找包含指定控制参数的实验。"""
        for result in exp_result.values():
            if param_name in result.params:
                return result
        return None

    def query_user_coupons(
        self, user_id: str, status_filter: str = "all",
        page: int = 1, page_size: int = 20,
    ) -> dict:
        """查询用户优惠券列表"""
        if not user_id:
            return {
                "code": CouponError.INVALID_PARAM,
                "message": "user_id不能为空",
                "coupons": [],
                "total": 0,
            }

        instance_ids = self.redis.get_user_coupons(user_id)
        coupons = []
        for iid in instance_ids:
            data = self.redis.get_coupon_instance(iid)
            if data:
                if status_filter != "all" and data.get("status") != status_filter:
                    continue
                coupons.append(data)

        coupons.sort(key=lambda x: x.get("claim_time", 0), reverse=True)
        total = len(coupons)
        start = (page - 1) * page_size
        page_coupons = coupons[start:start + page_size]

        return {
            "code": CouponError.OK,
            "message": CouponError.MESSAGES[CouponError.OK],
            "coupons": page_coupons,
            "total": total,
        }

    # ========== 内部方法 ==========

    def _call_scoring(
        self, user_id: str, scene_id: int,
        user_features: dict, context: dict, items: list,
        external: int, req_id: str,
    ):
        """调用打分服务，成功返回 list，失败返回 _ScoringFailure"""
        try:
            return self.scoring_client.score(
                user_id=user_id,
                scene_id=scene_id,
                user_features=user_features,
                context_features=context,
                items=items,
                external=external,
                request_id=req_id,
            )
        except TimeoutError:
            logger.error("打分服务超时")
            return _ScoringFailure.TIMEOUT
        except RuntimeError:
            logger.error("打分服务不可用")
            return _ScoringFailure.UNAVAILABLE

    def _do_claim(
        self, user_id: str, results: list, items: list, max_claim_per_request: int,
    ) -> Optional[dict]:
        """发放最优券：选分数最高的推荐券进行库存扣减和记录"""
        recommended = [r for r in results if r["recommended"]]
        if not recommended:
            return None

        recommended.sort(key=lambda r: r["calibrated_score"], reverse=True)
        items_map = {item["item_id"]: item for item in items}

        for best in recommended[:max_claim_per_request]:
            item = items_map.get(best["item_id"])
            if item is None:
                continue

            # 库存扣减
            remaining = self.redis.decr_stock(best["item_id"])
            if remaining < 0:
                logger.info("库存不足: item_id=%s", best["item_id"])
                continue

            # 记录领取
            instance_id = str(uuid.uuid4())
            now = int(time.time())
            expire_days = item.get("expire_days", 7)
            coupon_data = {
                "instance_id": instance_id,
                "item_id": best["item_id"],
                "user_id": user_id,
                "status": "claimed",
                "coupon_type": item.get("coupon_type", ""),
                "value": item.get("value", 0),
                "min_spend": item.get("min_spend", 0),
                "expire_time": now + expire_days * 86400,
                "claim_time": now,
            }

            self.redis.record_claim(user_id, best["item_id"], self.config.redis.user_claim_ttl)
            self.redis.save_coupon_instance(instance_id, coupon_data, expire_days * 86400)
            self.redis.add_user_coupon(user_id, instance_id, expire_days * 86400)

            logger.info("发放成功: user=%s, item=%s, instance=%s", user_id, best["item_id"], instance_id)
            return coupon_data

        return None

    def _build_fallback_response(
        self, user_id: str, items: list, scene_id: int,
        fallback_score: float, experiment_info: dict,
        score_threshold: float, max_claim_per_request: int,
    ) -> dict:
        """构建兜底响应"""
        results = [
            {
                "item_id": item["item_id"],
                "score": fallback_score,
                "calibrated_score": fallback_score,
                "recommended": fallback_score >= score_threshold,
            }
            for item in items
        ]

        coupon = self._do_claim(user_id, results, items, max_claim_per_request) if results else None

        return {
            "code": CouponError.OK,
            "message": "兜底策略",
            "scene_id": scene_id,
            "experiment_info": experiment_info,
            "results": results,
            "coupon": coupon,
        }

    def _resolve_claim_controls(
        self,
        external: Optional[int],
        score_threshold: Optional[float],
        max_claim_per_request: Optional[int],
    ) -> Optional[tuple[float, int]]:
        if external is None or score_threshold is None or max_claim_per_request is None:
            return None
        if external not in (0, 1):
            return None

        resolved_threshold = float(score_threshold)
        resolved_max_claim = int(max_claim_per_request)

        if not (0.0 <= resolved_threshold <= 1.0):
            return None
        if resolved_max_claim < 1:
            return None
        return resolved_threshold, resolved_max_claim

    def _resolve_fallback_score(self, scene_id: int, default_score: float) -> float:
        redis_score = self.redis.get_fallback_score(scene_id=scene_id)
        if redis_score is not None:
            return redis_score
        return default_score

    def _error(self, code: int) -> dict:
        return {
            "code": code,
            "message": CouponError.MESSAGES.get(code, "未知错误"),
            "scene_id": 0,
            "experiment_info": {},
            "results": [],
            "coupon": None,
        }
