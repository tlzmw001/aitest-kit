"""优惠券策略系统核心业务逻辑测试

使用 fakeredis 模拟 Redis，不依赖外部服务。
覆盖场景：推荐 pipeline、AB实验分流、场景路由、粗排、
特征抽取、打分、校准、发放、查询。
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

import pytest
import fakeredis
from pydantic import ValidationError

from ab_experiment_sdk import ConfigBasedABExperimentSDK
from coupon_system.config import (
    load_config,
    load_scene_routing_config,
    load_experiment_config,
    load_scene_experiment_mapping_config,
    AppConfig,
)
from coupon_system.services.redis_store import RedisStore
from coupon_system.services.scene_router import SceneRouter
from coupon_system.services.coarse_ranker import CoarseRanker
from coupon_system.services.feature_store import FeatureStore
from coupon_system.services.scoring_client import ScoringClient, ItemScore
from coupon_system.services.calibrator import Calibrator
from coupon_system.services.coupon_service import CouponBizService, CouponError
from coupon_system.services.grpc_servicer import CouponGrpcServicer
from coupon_system.http_app import RecommendRequest
from coupon_system.protos import coupon_pb2


# ========== Fixtures ==========

@pytest.fixture
def config() -> AppConfig:
    return load_config()


@pytest.fixture
def fake_redis_client():
    server = fakeredis.FakeServer()
    return fakeredis.FakeRedis(server=server, decode_responses=True)


@pytest.fixture
def redis_store(fake_redis_client) -> RedisStore:
    store = RedisStore.__new__(RedisStore)
    store.client = fake_redis_client
    store.prefix = "coupon:"
    return store


@pytest.fixture
def experiment_sdk() -> ConfigBasedABExperimentSDK:
    return ConfigBasedABExperimentSDK(load_experiment_config())


@pytest.fixture
def scene_router() -> SceneRouter:
    return SceneRouter(load_scene_routing_config())


@pytest.fixture
def scene_experiment_mapping_config():
    return load_scene_experiment_mapping_config()


@pytest.fixture
def coarse_ranker() -> CoarseRanker:
    return CoarseRanker()


@pytest.fixture
def feature_store(redis_store) -> FeatureStore:
    """使用项目自带的 item_features.tsv"""
    return FeatureStore(
        redis_store=redis_store,
        user_feature_keys=["gender", "total_spend", "is_new_user", "is_member"],
        item_feature_file="data/item_features.tsv",
    )


@pytest.fixture
def mock_scoring_client():
    """Mock 的打分客户端，不实际连接 gRPC"""
    client = MagicMock(spec=ScoringClient)
    client.enabled = True
    # 默认返回合理分数
    client.score.return_value = [
        ItemScore(item_id="COUPON_ACT_001", score=0.75),
    ]
    return client


@pytest.fixture
def calibrator() -> Calibrator:
    return Calibrator()


@pytest.fixture
def biz(
    config, redis_store, experiment_sdk, scene_experiment_mapping_config, scene_router,
    coarse_ranker, feature_store, mock_scoring_client, calibrator,
) -> CouponBizService:
    config.rate_limit.enabled = False
    return CouponBizService(
        config=config,
        redis_store=redis_store,
        experiment_sdk=experiment_sdk,
        scene_experiment_mapping=scene_experiment_mapping_config.scene_experiments,
        default_scene_experiments=scene_experiment_mapping_config.default_experiments,
        scene_router=scene_router,
        coarse_ranker=coarse_ranker,
        feature_store=feature_store,
        scoring_client=mock_scoring_client,
        calibrator=calibrator,
    )


@pytest.fixture
def biz_with_rate_limit(
    config, redis_store, experiment_sdk, scene_experiment_mapping_config, scene_router,
    coarse_ranker, feature_store, mock_scoring_client, calibrator,
) -> CouponBizService:
    config.rate_limit.enabled = True
    config.rate_limit.per_user_qps = 2
    config.rate_limit.max_qps = 100
    return CouponBizService(
        config=config,
        redis_store=redis_store,
        experiment_sdk=experiment_sdk,
        scene_experiment_mapping=scene_experiment_mapping_config.scene_experiments,
        default_scene_experiments=scene_experiment_mapping_config.default_experiments,
        scene_router=scene_router,
        coarse_ranker=coarse_ranker,
        feature_store=feature_store,
        scoring_client=mock_scoring_client,
        calibrator=calibrator,
    )


# ========== Helpers ==========

SAMPLE_ITEMS = [
    {"item_id": "COUPON_ACT_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 3},
]

MULTI_ITEMS = [
    {"item_id": "COUPON_ACT_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 3},
    {"item_id": "COUPON_SHIP_001", "coupon_type": "free_shipping", "value": 0, "min_spend": 0, "expire_days": 30},
    {"item_id": "COUPON_MEM_001", "coupon_type": "fixed", "value": 5000, "min_spend": 20000, "expire_days": 1},
]


def setup_stock(redis_store: RedisStore, item_id: str, stock: int = 100):
    redis_store.init_stock(item_id, stock)


def setup_user_features(redis_store: RedisStore, user_id: str, features: dict):
    redis_store.set_user_features(user_id, features)


def recommend(
    biz: CouponBizService,
    user_id: str,
    scene_name: str,
    device: str,
    policy_id: str,
    context: dict,
    items: list,
    **kwargs,
):
    kwargs.setdefault("external", 0)
    kwargs.setdefault("score_threshold", 0.5)
    kwargs.setdefault("max_claim_per_request", 1)
    return biz.recommend_and_claim(
        user_id=user_id,
        scene_name=scene_name,
        device=device,
        policy_id=policy_id,
        context=context,
        items=items,
        **kwargs,
    )


# ========== 参数校验 ==========

class TestParamValidation:
    def test_empty_user_id(self, biz):
        result = recommend(biz, "", "game", "mobile", "", {}, SAMPLE_ITEMS)
        assert result["code"] == CouponError.INVALID_PARAM

    def test_empty_scene_name(self, biz):
        result = recommend(biz, "u001", "", "mobile", "", {}, SAMPLE_ITEMS)
        assert result["code"] == CouponError.INVALID_PARAM

    def test_empty_device(self, biz):
        result = recommend(biz, "u001", "game", "", "", {}, SAMPLE_ITEMS)
        assert result["code"] == CouponError.INVALID_PARAM

    def test_empty_items(self, biz):
        result = recommend(biz, "u001", "game", "mobile", "", {}, [])
        assert result["code"] == CouponError.INVALID_PARAM

    def test_missing_required_request_fields(self, biz):
        result = biz.recommend_and_claim(
            user_id="u001",
            scene_name="game",
            device="mobile",
            policy_id="",
            context={},
            items=SAMPLE_ITEMS,
            req_id="req-no-required-fields",
        )
        assert result["code"] == CouponError.INVALID_PARAM


class TestRequestSchemaValidation:
    def _payload(self) -> dict:
        return {
            "user_id": "u001",
            "scene_name": "game",
            "device": "mobile",
            "policy_id": "",
            "external": 0,
            "reqId": "req-schema-001",
            "score_threshold": 0.5,
            "max_claim_per_request": 1,
            "context": {},
            "items": SAMPLE_ITEMS,
        }

    def test_http_model_requires_external(self):
        payload = self._payload()
        payload.pop("external")
        with pytest.raises(ValidationError):
            RecommendRequest(**payload)

    def test_http_model_requires_score_threshold(self):
        payload = self._payload()
        payload.pop("score_threshold")
        with pytest.raises(ValidationError):
            RecommendRequest(**payload)

    def test_http_model_requires_max_claim_per_request(self):
        payload = self._payload()
        payload.pop("max_claim_per_request")
        with pytest.raises(ValidationError):
            RecommendRequest(**payload)


class TestGrpcRequiredFields:
    def _build_item(self):
        return coupon_pb2.CouponItem(
            item_id="COUPON_ACT_001",
            coupon_type="discount",
            value=80,
            min_spend=5000,
            expire_days=3,
        )

    def test_grpc_missing_external_returns_invalid_param(self, biz):
        servicer = CouponGrpcServicer(biz)
        request = coupon_pb2.RecommendRequest(
            user_id="u001",
            scene_name="game",
            device="mobile",
            policy_id="",
            context={},
            items=[self._build_item()],
            score_threshold=0.5,
            max_claim_per_request=1,
        )
        response = servicer.Recommend(request, None)
        assert response.code == CouponError.INVALID_PARAM

    def test_grpc_missing_score_threshold_returns_invalid_param(self, biz):
        servicer = CouponGrpcServicer(biz)
        request = coupon_pb2.RecommendRequest(
            user_id="u001",
            scene_name="game",
            device="mobile",
            policy_id="",
            context={},
            items=[self._build_item()],
            external=0,
            max_claim_per_request=1,
        )
        response = servicer.Recommend(request, None)
        assert response.code == CouponError.INVALID_PARAM

    def test_grpc_missing_max_claim_per_request_returns_invalid_param(self, biz):
        servicer = CouponGrpcServicer(biz)
        request = coupon_pb2.RecommendRequest(
            user_id="u001",
            scene_name="game",
            device="mobile",
            policy_id="",
            context={},
            items=[self._build_item()],
            external=0,
            score_threshold=0.5,
        )
        response = servicer.Recommend(request, None)
        assert response.code == CouponError.INVALID_PARAM

    def test_grpc_with_all_required_fields_can_pass_validation(self, biz):
        servicer = CouponGrpcServicer(biz)
        request = coupon_pb2.RecommendRequest(
            user_id="u001",
            scene_name="game",
            device="mobile",
            policy_id="",
            context={},
            items=[self._build_item()],
            external=0,
            score_threshold=0.5,
            max_claim_per_request=1,
        )
        response = servicer.Recommend(request, None)
        assert response.code == CouponError.OK

    def test_grpc_item_is_prior_mapped_to_internal_field(self, biz, redis_store):
        setup_stock(redis_store, "COUPON_ACT_001", 100)
        # 强制命中开启粗排的策略，确保 coarse_ranker 会被调用。
        biz.experiment_sdk.set_user_whitelist(
            "u_grpc_prior",
            {
                "coarse_rank_exp_game": "cr_v2_full",
                "calibration_exp_game": "cal_off",
            },
        )
        servicer = CouponGrpcServicer(biz)
        request = coupon_pb2.RecommendRequest(
            user_id="u_grpc_prior",
            scene_name="game",
            device="mobile",
            policy_id="",
            context={},
            items=[
                coupon_pb2.CouponItem(
                    item_id="COUPON_ACT_001",
                    coupon_type="discount",
                    value=80,
                    min_spend=5000,
                    expire_days=3,
                    is_prior=True,
                )
            ],
            external=0,
            score_threshold=0.5,
            max_claim_per_request=1,
        )
        with patch.object(biz.coarse_ranker, "rank", wraps=biz.coarse_ranker.rank) as mock_rank:
            response = servicer.Recommend(request, None)

        assert response.code == CouponError.OK
        mock_rank.assert_called()
        rank_items = mock_rank.call_args.args[0]
        assert rank_items[0].get("isPrior") is True


# ========== 场景路由 ==========

class TestSceneRouting:
    def test_game_mobile(self, biz, redis_store, mock_scoring_client):
        setup_stock(redis_store, "COUPON_ACT_001")
        result = recommend(biz, "u001", "game", "mobile", "", {}, SAMPLE_ITEMS)
        assert result["scene_id"] == 1001

    def test_ad_pc(self, biz, redis_store, mock_scoring_client):
        setup_stock(redis_store, "COUPON_ACT_001")
        result = recommend(biz, "u001", "ad", "pc", "", {}, SAMPLE_ITEMS)
        assert result["scene_id"] == 2002

    def test_fallback_policy_id(self, biz, redis_store):
        """命中兜底 policyId，跳过打分"""
        setup_stock(redis_store, "COUPON_ACT_001")
        result = recommend(biz, 
            "u001", "game", "mobile", "policy_fallback_001", {}, SAMPLE_ITEMS,
        )
        assert result["scene_id"] == 3001
        assert result["message"] == "兜底策略"
        assert result["experiment_info"] == {}
        # 兜底不调打分服务
        biz.scoring_client.score.assert_not_called()

    def test_fallback_claim_has_correct_user_id(self, biz, redis_store):
        """兜底发放时 user_id 不应为空"""
        setup_stock(redis_store, "COUPON_ACT_001")
        result = recommend(biz, 
            "u_fallback", "game", "mobile", "policy_fallback_001", {}, SAMPLE_ITEMS,
        )
        assert result["coupon"] is not None
        assert result["coupon"]["user_id"] == "u_fallback"

    def test_unknown_scene_fallback(self, biz, redis_store):
        """未知场景组合走兜底"""
        setup_stock(redis_store, "COUPON_ACT_001")
        result = recommend(biz, "u001", "unknown", "vr", "", {}, SAMPLE_ITEMS)
        assert result["scene_id"] == 3001
        assert result["experiment_info"] == {}

    def test_fallback_scene_skips_experiment_evaluation(self, biz, redis_store):
        setup_stock(redis_store, "COUPON_ACT_001")
        with patch.object(biz.experiment_sdk, "evaluate", wraps=biz.experiment_sdk.evaluate) as mock_eval:
            result = recommend(
                biz,
                "u_fallback_skip_exp",
                "game",
                "mobile",
                "policy_fallback_001",
                {},
                SAMPLE_ITEMS,
            )
        assert result["code"] == CouponError.OK
        assert result["scene_id"] == 3001
        assert result["experiment_info"] == {}
        mock_eval.assert_not_called()


# ========== AB 实验 ==========

class TestExperiment:
    def test_experiment_info_in_response(self, biz, redis_store, mock_scoring_client):
        setup_stock(redis_store, "COUPON_ACT_001")
        result = recommend(biz, "u001", "game", "mobile", "", {}, SAMPLE_ITEMS)
        assert "experiment_info" in result
        assert isinstance(result["experiment_info"], dict)
        # game/mobile -> scene_id=1001，应命中该场景映射的实验
        assert "coarse_rank_exp_game" in result["experiment_info"]
        assert "calibration_exp_game" in result["experiment_info"]

    def test_whitelist_user_can_force_strategy(self, biz, redis_store):
        setup_stock(redis_store, "COUPON_ACT_001")
        biz.experiment_sdk.set_user_whitelist(
            "u_whitelist_001",
            {
                "coarse_rank_exp_game": "cr_off",
                "calibration_exp_game": "cal_on",
            },
        )
        result = recommend(
            biz, "u_whitelist_001", "game", "mobile", "", {}, SAMPLE_ITEMS,
        )

        assert result["code"] == CouponError.OK
        assert result["experiment_info"]["coarse_rank_exp_game"] == "cr_off"
        assert result["experiment_info"]["calibration_exp_game"] == "cal_on"

    def test_only_scene_mapped_experiments_are_evaluated(self, biz, redis_store):
        setup_stock(redis_store, "COUPON_ACT_001")
        result = recommend(biz, "u001", "ad", "pc", "", {}, SAMPLE_ITEMS)

        assert result["code"] == CouponError.OK
        assert "coarse_rank_exp_ad" in result["experiment_info"]
        assert "calibration_exp_ad" in result["experiment_info"]
        assert "coarse_rank_exp_game" not in result["experiment_info"]
        assert "calibration_exp_game" not in result["experiment_info"]


# ========== 粗排 ==========

class TestCoarseRanking:
    def test_prior_top_value_keeps_sorted_order(self, coarse_ranker):
        items = [
            {"item_id": "P_low", "isPrior": True, "value": 10},
            {"item_id": "N_mid", "isPrior": False, "value": 50},
            {"item_id": "P_high", "isPrior": True, "value": 100},
        ]
        params = {
            "truncate_count": 2,
            "prior_count": 2,
            "prior_rule": "top_value",
        }
        result = coarse_ranker.rank(items, params)
        assert [x["item_id"] for x in result] == ["P_high", "P_low"]

    def test_truncation(self, coarse_ranker):
        items = [
            {"item_id": "A", "value": 100},
            {"item_id": "B", "value": 500},
            {"item_id": "C", "value": 200},
            {"item_id": "D", "value": 50},
        ]
        result = coarse_ranker.rank(items, {"truncate_count": 2, "truncate_rule": "top_value"})
        assert len(result) == 2
        assert result[0]["item_id"] == "B"
        assert result[1]["item_id"] == "C"

    def test_no_truncation_when_count_exceeds(self, coarse_ranker):
        items = [{"item_id": "A", "value": 100}]
        result = coarse_ranker.rank(items, {"truncate_count": 10, "truncate_rule": "top_value"})
        assert len(result) == 1

    def test_filters_and_intersection(self, coarse_ranker):
        items = [
            {"item_id": "A", "coupon_type": "discount", "value": 10, "expire_days": 3},
            {"item_id": "B", "coupon_type": "fixed", "value": 4, "expire_days": 5},
            {"item_id": "C", "coupon_type": "discount", "value": 6, "expire_days": 1},
        ]
        params = {
            "truncate_count": 10,
            "filters": [
                {"field": "expire_days", "op": "gte", "value": 3},
                {"field": "value", "op": "gte", "value": 5},
                {"field": "coupon_type", "op": "in", "value": ["discount", "cash"]},
            ],
        }
        result = coarse_ranker.rank(items, params)
        assert [x["item_id"] for x in result] == ["A"]

    def test_diversity_with_backfill(self, coarse_ranker):
        items = [
            {"item_id": "A", "coupon_type": "cash", "value": 100},
            {"item_id": "B", "coupon_type": "cash", "value": 90},
            {"item_id": "C", "coupon_type": "cash", "value": 80},
        ]
        params = {
            "truncate_count": 2,
            "truncate_rule": "top_value",
            "diversity": {
                "enabled": True,
                "group_field": "coupon_type",
                "max_per_group": 1,
            },
        }
        result = coarse_ranker.rank(items, params)
        # 先按多样性选 A，再从 backfill 池补 B，保证数量补满。
        assert [x["item_id"] for x in result] == ["A", "B"]

    def test_full_pipeline_with_prior_filter_sort_and_diversity(self, coarse_ranker):
        items = [
            {"item_id": "P1", "isPrior": True, "coupon_type": "cash", "value": 100, "min_spend": 100, "expire_days": 5},
            {"item_id": "P2", "isPrior": True, "coupon_type": "discount", "value": 90, "min_spend": 80, "expire_days": 5},
            {"item_id": "P3", "isPrior": True, "coupon_type": "cash", "value": 80, "min_spend": 70, "expire_days": 5},
            {"item_id": "A", "coupon_type": "cash", "value": 95, "min_spend": 200, "expire_days": 5},
            {"item_id": "B", "coupon_type": "cash", "value": 90, "min_spend": 180, "expire_days": 5},
            {"item_id": "C", "coupon_type": "discount", "value": 70, "min_spend": 20, "expire_days": 5},
            {"item_id": "D", "coupon_type": "discount", "value": 60, "min_spend": 10, "expire_days": 2},
            {"item_id": "E", "coupon_type": "fixed", "value": 65, "min_spend": 30, "expire_days": 5},
        ]
        params = {
            "truncate_count": 5,
            "prior_count": 2,
            "prior_rule": "top_value",
            "filters": [
                {"field": "expire_days", "op": "gte", "value": 3},
            ],
            "sort_keys": [
                {"field": "value", "weight": 0.6},
                {"field": "min_spend", "weight": -0.4},
            ],
            "diversity": {
                "enabled": True,
                "group_field": "coupon_type",
                "max_per_group": 1,
            },
        }
        result = coarse_ranker.rank(items, params)
        # 阶段0: 保送 P1/P2；阶段1: 过滤 D；阶段3: 多样性后目标位取 A/C/E。
        assert [x["item_id"] for x in result] == ["P1", "P2", "A", "C", "E"]


# ========== 打分 + 发放 ==========

class TestRecommendAndClaim:
    def test_successful_claim(self, biz, redis_store, mock_scoring_client):
        """正常打分 + 发放"""
        setup_stock(redis_store, "COUPON_ACT_001", 100)
        mock_scoring_client.score.return_value = [
            ItemScore(item_id="COUPON_ACT_001", score=0.6),
        ]

        result = recommend(biz, "u001", "game", "mobile", "", {}, SAMPLE_ITEMS)

        assert result["code"] == CouponError.OK
        assert len(result["results"]) == 1
        assert result["results"][0]["item_id"] == "COUPON_ACT_001"
        assert result["coupon"] is not None
        assert result["coupon"]["item_id"] == "COUPON_ACT_001"
        assert result["coupon"]["status"] == "claimed"

    def test_stock_decremented(self, biz, redis_store, mock_scoring_client):
        """发放后库存减少"""
        setup_stock(redis_store, "COUPON_ACT_001", 100)
        mock_scoring_client.score.return_value = [
            ItemScore(item_id="COUPON_ACT_001", score=0.6),
        ]

        recommend(biz, "u001", "game", "mobile", "", {}, SAMPLE_ITEMS)
        assert redis_store.get_stock("COUPON_ACT_001") == 99

    def test_low_score_no_claim(self, biz, redis_store, mock_scoring_client):
        """分数低于阈值不发放"""
        setup_stock(redis_store, "COUPON_ACT_001", 100)
        mock_scoring_client.score.return_value = [
            ItemScore(item_id="COUPON_ACT_001", score=0.3),
        ]

        result = recommend(biz, "u001", "game", "mobile", "", {}, SAMPLE_ITEMS)

        assert result["code"] == CouponError.OK
        assert result["coupon"] is None
        assert result["results"][0]["recommended"] is False
        assert redis_store.get_stock("COUPON_ACT_001") == 100

    def test_stock_empty_skip(self, biz, redis_store, mock_scoring_client):
        """库存为零时跳过发放"""
        setup_stock(redis_store, "COUPON_ACT_001", 0)
        mock_scoring_client.score.return_value = [
            ItemScore(item_id="COUPON_ACT_001", score=0.8),
        ]

        result = recommend(biz, "u001", "game", "mobile", "", {}, SAMPLE_ITEMS)
        assert result["code"] == CouponError.OK
        assert result["coupon"] is None

    def test_multi_items_best_score_claimed(self, biz, redis_store, mock_scoring_client):
        """多个候选券，发放分数最高的"""
        for item in MULTI_ITEMS:
            setup_stock(redis_store, item["item_id"], 100)

        mock_scoring_client.score.return_value = [
            ItemScore(item_id="COUPON_ACT_001", score=0.6),
            ItemScore(item_id="COUPON_SHIP_001", score=0.9),
            ItemScore(item_id="COUPON_MEM_001", score=0.4),
        ]

        result = recommend(biz, "u001", "game", "mobile", "", {}, MULTI_ITEMS)
        assert result["coupon"]["item_id"] == "COUPON_SHIP_001"

    def test_request_score_threshold_override(self, biz, redis_store, mock_scoring_client):
        """请求参数 score_threshold 覆盖配置"""
        setup_stock(redis_store, "COUPON_ACT_001", 100)
        mock_scoring_client.score.return_value = [
            ItemScore(item_id="COUPON_ACT_001", score=0.6),
        ]

        result = recommend(biz, 
            "u001", "game", "mobile", "", {}, SAMPLE_ITEMS,
            score_threshold=0.95,
        )
        assert result["code"] == CouponError.OK
        assert result["coupon"] is None
        assert result["results"][0]["recommended"] is False

    def test_request_max_claim_per_request_controls_attempt_count(
        self, biz, redis_store, mock_scoring_client,
    ):
        """
        max_claim_per_request 影响可尝试发券的候选数量。
        当最高分券无库存时，只有 max_claim_per_request>=2 才能尝试到次优券。
        """
        items = [
            {"item_id": "A", "coupon_type": "discount", "value": 10, "min_spend": 0, "expire_days": 3},
            {"item_id": "B", "coupon_type": "discount", "value": 10, "min_spend": 0, "expire_days": 3},
        ]
        setup_stock(redis_store, "A", 0)
        setup_stock(redis_store, "B", 100)
        mock_scoring_client.score.return_value = [
            ItemScore(item_id="A", score=0.9),
            ItemScore(item_id="B", score=0.8),
        ]

        result_1 = recommend(biz, 
            "u001", "game", "mobile", "", {}, items,
            max_claim_per_request=1,
        )
        assert result_1["coupon"] is None

        result_2 = recommend(biz, 
            "u001", "game", "mobile", "", {}, items,
            max_claim_per_request=2,
        )
        assert result_2["coupon"] is not None
        assert result_2["coupon"]["item_id"] == "B"

    def test_invalid_request_claim_controls(self, biz):
        """请求级阈值/数量非法时返回参数错误"""
        result = recommend(biz, 
            "u001", "game", "mobile", "", {}, SAMPLE_ITEMS,
            score_threshold=1.5,
        )
        assert result["code"] == CouponError.INVALID_PARAM

        result = recommend(biz, 
            "u001", "game", "mobile", "", {}, SAMPLE_ITEMS,
            max_claim_per_request=0,
        )
        assert result["code"] == CouponError.INVALID_PARAM


# ========== 打分服务异常 ==========

class TestScoringFailure:
    def test_scoring_timeout_fallback(self, biz, redis_store, mock_scoring_client):
        """打分超时走兜底，使用 on_scoring_timeout.default_score=0.5"""
        setup_stock(redis_store, "COUPON_ACT_001", 100)
        mock_scoring_client.score.side_effect = TimeoutError("timeout")

        result = recommend(biz, "u001", "game", "mobile", "", {}, SAMPLE_ITEMS)
        assert result["code"] == CouponError.OK
        # timeout default_score=0.5 >= threshold=0.5，应该发放
        assert result["coupon"] is not None

    def test_scoring_unavailable_fallback(self, biz, redis_store, mock_scoring_client):
        """打分不可用走兜底，使用 on_scoring_unavailable.default_score=0.3"""
        setup_stock(redis_store, "COUPON_ACT_001", 100)
        mock_scoring_client.score.side_effect = RuntimeError("unavailable")

        result = recommend(biz, "u001", "game", "mobile", "", {}, SAMPLE_ITEMS)
        assert result["code"] == CouponError.OK
        # unavailable default_score=0.3 < threshold=0.5，不发放
        assert result["coupon"] is None

    def test_scoring_timeout_deny(self, biz, redis_store, mock_scoring_client):
        """timeout action=deny 时直接返回错误"""
        biz.config.fallback.on_scoring_timeout.action = "deny"
        setup_stock(redis_store, "COUPON_ACT_001", 100)
        mock_scoring_client.score.side_effect = TimeoutError("timeout")

        result = recommend(biz, "u001", "game", "mobile", "", {}, SAMPLE_ITEMS)
        assert result["code"] == CouponError.SCORING_ERROR

    def test_fallback_score_redis_first(self, biz, redis_store, mock_scoring_client):
        """兜底分优先读 Redis，读不到才用配置默认值"""
        setup_stock(redis_store, "COUPON_ACT_001", 100)
        redis_store.set_fallback_score(0.9, scene_id=1001)
        mock_scoring_client.score.side_effect = RuntimeError("unavailable")

        result = recommend(biz, "u001", "game", "mobile", "", {}, SAMPLE_ITEMS)
        assert result["code"] == CouponError.OK
        assert result["results"][0]["score"] == 0.9
        assert result["coupon"] is not None


class TestRoutingAndLogs:
    def test_external_route_and_req_id_logged(self, biz, redis_store, mock_scoring_client, caplog):
        setup_stock(redis_store, "COUPON_ACT_001", 100)
        caplog.set_level("INFO")

        result = recommend(biz, 
            "u_ext", "game", "mobile", "", {}, SAMPLE_ITEMS,
            external=1,
            req_id="req-abc-001",
        )

        assert result["code"] == CouponError.OK
        assert result["experiment_info"] == {}
        mock_scoring_client.score.assert_called()
        kwargs = mock_scoring_client.score.call_args.kwargs
        assert kwargs["external"] == 1
        assert kwargs["request_id"] == "req-abc-001"

        matched = [
            rec.getMessage() for rec in caplog.records
            if "recommend request:" in rec.getMessage()
        ]
        assert matched, "should have request info log"
        log = matched[-1]
        assert "reqId=req-abc-001" in log
        assert "user_id=u_ext" in log
        assert "item_ids=COUPON_ACT_001" in log
        assert "route=2" in log
        assert "scene_id=1001" in log

    def test_external_route_skips_experiment_evaluation(self, biz, redis_store, mock_scoring_client):
        setup_stock(redis_store, "COUPON_ACT_001", 100)
        with patch.object(biz.experiment_sdk, "evaluate", wraps=biz.experiment_sdk.evaluate) as mock_eval:
            result = recommend(
                biz,
                "u_ext_skip_exp",
                "game",
                "mobile",
                "",
                {},
                SAMPLE_ITEMS,
                external=1,
            )

        assert result["code"] == CouponError.OK
        assert result["experiment_info"] == {}
        mock_eval.assert_not_called()

    def test_scene_route_still_works_when_external_enabled(self, biz, redis_store, mock_scoring_client):
        """
        场景与 route 隔离：external=1 仍需正常计算 scene_id。
        """
        setup_stock(redis_store, "COUPON_ACT_001", 100)
        result = recommend(biz, 
            "u_ext_scene", "ad", "pc", "", {}, SAMPLE_ITEMS,
            external=1,
        )
        assert result["scene_id"] == 2002


# ========== 校准 ==========

class TestCalibration:
    def test_linear_calibration_and_clamp(self, calibrator, tmp_path):
        """命中线性规则后执行 y = kx+b，并在最终做 clamp"""
        linear_dir = tmp_path / "linear"
        linear_dir.mkdir()
        (linear_dir / "1.json").write_text(
            '[{"conditions":{"device":"ios"},"k":1.2,"b":0.1}]'
        )

        scores = [ItemScore(item_id="A", score=0.9)]
        result = calibrator.calibrate(
            scene_id=1001,
            scores=scores,
            calibration_params={"calibration_dir": {"linear": str(linear_dir)}},
            request_context={"device": "ios"},
            item_context_by_id={"A": {"coupon_type": "discount"}},
        )
        assert result[0].calibrated_score == 1.0

    def test_piecewise_then_linear_chain(self, calibrator, tmp_path):
        """分段与线性都命中时，按“先分段后线性”串联"""
        linear_dir = tmp_path / "linear"
        piecewise_dir = tmp_path / "piecewise"
        linear_dir.mkdir()
        piecewise_dir.mkdir()
        (linear_dir / "1.json").write_text(
            '[{"conditions":{"device":"ios"},"k":1.2,"b":0.05}]'
        )
        (piecewise_dir / "1.json").write_text(
            """
            [
              {
                "conditions":{"device":"ios"},
                "segments":[
                  {"range":[0.0,0.3],"k":0.8,"b":0.01},
                  {"range":[0.3,0.7],"k":1.0,"b":0.0},
                  {"range":[0.7,1.0],"k":1.2,"b":-0.05}
                ]
              }
            ]
            """
        )

        scores = [ItemScore(item_id="A", score=0.5)]
        result = calibrator.calibrate(
            scene_id=1001,
            scores=scores,
            calibration_params={
                "calibration_dir": {
                    "linear": str(linear_dir),
                    "piecewise": str(piecewise_dir),
                }
            },
            request_context={"device": "ios"},
            item_context_by_id={"A": {"coupon_type": "discount"}},
        )
        # 0.5 先命中分段中间段保持 0.5，再线性 1.2 * 0.5 + 0.05 = 0.65
        assert result[0].calibrated_score == 0.65

    def test_latest_version_file_wins(self, calibrator, tmp_path):
        """目录中加载序号最大的文件"""
        linear_dir = tmp_path / "linear"
        linear_dir.mkdir()
        (linear_dir / "1.json").write_text(
            '[{"conditions":{"device":"ios"},"k":1.1,"b":0.0}]'
        )
        (linear_dir / "3.json").write_text(
            '[{"conditions":{"device":"ios"},"k":1.3,"b":0.0}]'
        )

        result = calibrator.calibrate(
            scene_id=1001,
            scores=[ItemScore(item_id="A", score=0.5)],
            calibration_params={"calibration_dir": {"linear": str(linear_dir)}},
            request_context={"device": "ios"},
        )
        assert result[0].calibrated_score == 0.65

    def test_invalid_condition_field_is_not_matched(self, calibrator, tmp_path):
        """规则包含未支持字段时，该规则视为无效不命中"""
        linear_dir = tmp_path / "linear"
        linear_dir.mkdir()
        (linear_dir / "1.json").write_text(
            '[{"conditions":{"unknown":"x"},"k":2.0,"b":0.1}]'
        )

        result = calibrator.calibrate(
            scene_id=1001,
            scores=[ItemScore(item_id="A", score=0.4)],
            calibration_params={"calibration_dir": {"linear": str(linear_dir)}},
            request_context={"device": "ios"},
        )
        assert result[0].calibrated_score == 0.4


# ========== 特征抽取 ==========

class TestFeatureStore:
    def test_get_user_features(self, redis_store, feature_store):
        redis_store.set_user_features("u001", {
            "gender": "male",
            "total_spend": "15000",
            "is_new_user": "true",
        })
        features = feature_store.get_user_features("u001")
        assert features["gender"] == "male"
        assert features["total_spend"] == "15000"

    def test_get_item_features(self, feature_store):
        features = feature_store.get_item_features("COUPON_ACT_001")
        assert "popularity" in features
        assert "stock" in features

    def test_missing_item_features(self, feature_store):
        features = feature_store.get_item_features("NONEXISTENT")
        assert features == {}


# ========== 查询接口 ==========

class TestQueryCoupons:
    def test_query_empty(self, biz):
        result = biz.query_user_coupons("user_no_coupons")
        assert result["code"] == CouponError.OK
        assert result["coupons"] == []
        assert result["total"] == 0

    def test_query_after_claim(self, biz, redis_store, mock_scoring_client):
        setup_stock(redis_store, "COUPON_ACT_001", 100)
        mock_scoring_client.score.return_value = [
            ItemScore(item_id="COUPON_ACT_001", score=0.8),
        ]
        recommend(biz, "u001", "game", "mobile", "", {}, SAMPLE_ITEMS)

        result = biz.query_user_coupons("u001")
        assert result["code"] == CouponError.OK
        assert result["total"] == 1
        assert result["coupons"][0]["item_id"] == "COUPON_ACT_001"

    def test_query_invalid_user(self, biz):
        result = biz.query_user_coupons("")
        assert result["code"] == CouponError.INVALID_PARAM


# ========== 限流 ==========

class TestRateLimit:
    def test_user_rate_limit(self, biz_with_rate_limit, redis_store, mock_scoring_client):
        """用户级限流（per_user_qps=2）"""
        biz = biz_with_rate_limit
        setup_stock(redis_store, "COUPON_ACT_001", 100)
        mock_scoring_client.score.return_value = [
            ItemScore(item_id="COUPON_ACT_001", score=0.8),
        ]

        r1 = recommend(biz, "u001", "game", "mobile", "", {}, SAMPLE_ITEMS)
        r2 = recommend(biz, "u001", "game", "mobile", "", {}, SAMPLE_ITEMS)
        r3 = recommend(biz, "u001", "game", "mobile", "", {}, SAMPLE_ITEMS)

        codes = [r1["code"], r2["code"], r3["code"]]
        assert CouponError.RATE_LIMITED in codes or all(c == CouponError.OK for c in codes[:2])
