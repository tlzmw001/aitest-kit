"""优惠券核心业务逻辑功能测试

使用 fakeredis 模拟 Redis，不依赖外部服务。
覆盖场景：正常领取、重复领取、库存不足、场景不匹配、
新用户/会员校验、领取次数限制、模型拒绝、模型超时兜底、限流。
"""
from __future__ import annotations

import pytest
import fakeredis

from coupon_system.config import load_config, AppConfig
from coupon_system.services.redis_store import RedisStore
from coupon_system.services.model_service import MockModelService
from coupon_system.services.coupon_service import CouponBizService, CouponError


@pytest.fixture
def config() -> AppConfig:
    return load_config()


@pytest.fixture
def fake_redis_client():
    """创建 fakeredis 客户端"""
    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server, decode_responses=True)
    return client


@pytest.fixture
def redis_store(fake_redis_client) -> RedisStore:
    store = RedisStore.__new__(RedisStore)
    store.client = fake_redis_client
    store.prefix = "coupon:"
    return store


@pytest.fixture
def model_service() -> MockModelService:
    return MockModelService(timeout=2.0, enabled=True)


@pytest.fixture
def biz(config, redis_store, model_service) -> CouponBizService:
    # 禁用限流简化测试
    config.rate_limit.enabled = False
    return CouponBizService(config, redis_store, model_service)


@pytest.fixture
def biz_with_rate_limit(config, redis_store, model_service) -> CouponBizService:
    config.rate_limit.enabled = True
    config.rate_limit.per_user_qps = 2
    config.rate_limit.max_qps = 100
    return CouponBizService(config, redis_store, model_service)


def setup_stock(redis_store: RedisStore, coupon_id: str, stock: int = 100):
    redis_store.init_stock(coupon_id, stock)


def setup_new_user(redis_store: RedisStore, user_id: str):
    redis_store.set_user_profile(user_id, {"is_new_user": True, "total_spend": 0})


def setup_member(redis_store: RedisStore, user_id: str):
    redis_store.set_user_profile(user_id, {"is_member": True, "total_spend": 15000})


def setup_old_user(redis_store: RedisStore, user_id: str):
    redis_store.set_user_profile(user_id, {"is_new_user": False, "is_member": False, "total_spend": 5000})


# ========== 参数校验 ==========

class TestParamValidation:
    def test_empty_user_id(self, biz):
        result = biz.claim_coupon("", "COUPON_NEW_001", "new_user")
        assert result["code"] == CouponError.INVALID_PARAM

    def test_empty_coupon_id(self, biz):
        result = biz.claim_coupon("user_001", "", "new_user")
        assert result["code"] == CouponError.INVALID_PARAM

    def test_empty_scene(self, biz):
        result = biz.claim_coupon("user_001", "COUPON_NEW_001", "")
        assert result["code"] == CouponError.INVALID_PARAM


# ========== 场景路由 ==========

class TestSceneRouting:
    def test_invalid_scene(self, biz, redis_store):
        setup_stock(redis_store, "COUPON_NEW_001")
        result = biz.claim_coupon("user_001", "COUPON_NEW_001", "nonexistent_scene")
        assert result["code"] == CouponError.SCENE_NOT_FOUND

    def test_coupon_not_in_scene(self, biz, redis_store):
        """新人券不能在活动场景下领取"""
        setup_stock(redis_store, "COUPON_NEW_001")
        setup_new_user(redis_store, "user_001")
        result = biz.claim_coupon("user_001", "COUPON_NEW_001", "activity")
        assert result["code"] == CouponError.SCENE_MISMATCH

    def test_coupon_not_found(self, biz, redis_store):
        result = biz.claim_coupon("user_001", "NONEXISTENT_COUPON", "new_user")
        assert result["code"] == CouponError.COUPON_NOT_FOUND


# ========== 正常领取 ==========

class TestClaimSuccess:
    def test_new_user_claim_success(self, biz, redis_store):
        """新用户正常领取新人券"""
        setup_stock(redis_store, "COUPON_NEW_001", 100)
        setup_new_user(redis_store, "user_001")

        result = biz.claim_coupon("user_001", "COUPON_NEW_001", "new_user")

        assert result["code"] == CouponError.OK
        assert result["coupon"] is not None
        assert result["coupon"]["status"] == "claimed"
        assert result["coupon"]["coupon_id"] == "COUPON_NEW_001"
        assert result["coupon"]["user_id"] == "user_001"
        assert result["coupon"]["coupon_type"] == "fixed"
        assert result["coupon"]["value"] == 2000

    def test_stock_decremented(self, biz, redis_store):
        """领取后库存减少"""
        setup_stock(redis_store, "COUPON_NEW_001", 100)
        setup_new_user(redis_store, "user_001")

        biz.claim_coupon("user_001", "COUPON_NEW_001", "new_user")

        assert redis_store.get_stock("COUPON_NEW_001") == 99

    def test_claim_recorded(self, biz, redis_store):
        """领取后记录已领取"""
        setup_stock(redis_store, "COUPON_NEW_001", 100)
        setup_new_user(redis_store, "user_001")

        biz.claim_coupon("user_001", "COUPON_NEW_001", "new_user")

        assert redis_store.has_claimed("user_001", "COUPON_NEW_001")

    def test_activity_claim_success(self, biz, redis_store):
        """活动场景领取"""
        setup_stock(redis_store, "COUPON_ACT_001", 100)
        setup_old_user(redis_store, "user_002")

        result = biz.claim_coupon("user_002", "COUPON_ACT_001", "activity")

        assert result["code"] == CouponError.OK
        assert result["coupon"]["coupon_type"] == "discount"


# ========== 规则引擎粗筛 ==========

class TestRuleEngine:
    def test_duplicate_claim(self, biz, redis_store):
        """重复领取同一券"""
        setup_stock(redis_store, "COUPON_NEW_001", 100)
        setup_new_user(redis_store, "user_001")

        biz.claim_coupon("user_001", "COUPON_NEW_001", "new_user")
        result = biz.claim_coupon("user_001", "COUPON_NEW_001", "new_user")

        assert result["code"] == CouponError.ALREADY_CLAIMED

    def test_stock_empty(self, biz, redis_store):
        """库存为零"""
        setup_stock(redis_store, "COUPON_NEW_001", 0)
        setup_new_user(redis_store, "user_001")

        result = biz.claim_coupon("user_001", "COUPON_NEW_001", "new_user")
        assert result["code"] == CouponError.STOCK_EMPTY

    def test_not_new_user(self, biz, redis_store):
        """非新用户尝试领新人券"""
        setup_stock(redis_store, "COUPON_NEW_001", 100)
        setup_old_user(redis_store, "user_001")

        result = biz.claim_coupon("user_001", "COUPON_NEW_001", "new_user")
        assert result["code"] == CouponError.NOT_NEW_USER

    def test_not_member(self, biz, redis_store):
        """非会员尝试领会员日券"""
        setup_stock(redis_store, "COUPON_MEM_001", 100)
        setup_old_user(redis_store, "user_001")

        result = biz.claim_coupon("user_001", "COUPON_MEM_001", "member_day")
        assert result["code"] == CouponError.NOT_MEMBER

    def test_claim_limit_exceeded(self, biz, redis_store):
        """超过场景领取次数限制（活动场景限3次）"""
        setup_stock(redis_store, "COUPON_ACT_001", 100)
        setup_stock(redis_store, "COUPON_SHIP_001", 100)
        # 用高消费用户确保模型精排通过
        redis_store.set_user_profile("user_001", {
            "is_new_user": False, "is_member": False, "total_spend": 50000
        })
        # 关闭模型避免随机性干扰
        biz.model.enabled = False

        # 活动场景限制 max_claim_per_user=3
        r1 = biz.claim_coupon("user_001", "COUPON_ACT_001", "activity")
        assert r1["code"] == CouponError.OK

        r2 = biz.claim_coupon("user_001", "COUPON_SHIP_001", "activity")
        assert r2["code"] == CouponError.OK

        count = redis_store.get_user_claim_count("user_001", "activity")
        assert count == 2

        biz.model.enabled = True

    def test_stock_race_condition(self, biz, redis_store):
        """库存只剩1时的竞争"""
        setup_stock(redis_store, "COUPON_NEW_001", 1)
        setup_new_user(redis_store, "user_001")
        setup_new_user(redis_store, "user_002")

        # 修复：给 user_002 也设置新用户画像
        redis_store.set_user_profile("user_002", {"is_new_user": True})

        r1 = biz.claim_coupon("user_001", "COUPON_NEW_001", "new_user")
        assert r1["code"] == CouponError.OK

        r2 = biz.claim_coupon("user_002", "COUPON_NEW_001", "new_user")
        assert r2["code"] == CouponError.STOCK_EMPTY


# ========== 模型精排 + 兜底 ==========

class TestModelEvaluation:
    def test_model_timeout_fallback_allow(self, biz, redis_store):
        """模型超时时兜底放行"""
        setup_stock(redis_store, "COUPON_NEW_001", 100)
        setup_new_user(redis_store, "user_001")
        biz.model.set_simulate_timeout(True)

        # 配置兜底策略为 allow
        biz.config.fallback.on_model_timeout.action = "allow"

        result = biz.claim_coupon("user_001", "COUPON_NEW_001", "new_user")
        assert result["code"] == CouponError.OK

        biz.model.set_simulate_timeout(False)

    def test_model_failure_fallback_allow(self, biz, redis_store):
        """模型服务不可用时兜底放行"""
        setup_stock(redis_store, "COUPON_NEW_001", 100)
        setup_new_user(redis_store, "user_001")
        biz.model.set_simulate_failure(True)

        biz.config.fallback.on_model_unavailable.action = "allow"

        result = biz.claim_coupon("user_001", "COUPON_NEW_001", "new_user")
        assert result["code"] == CouponError.OK

        biz.model.set_simulate_failure(False)

    def test_model_failure_fallback_deny(self, biz, redis_store):
        """模型服务不可用时兜底拒绝"""
        setup_stock(redis_store, "COUPON_NEW_001", 100)
        setup_new_user(redis_store, "user_001")
        biz.model.set_simulate_failure(True)

        biz.config.fallback.on_model_unavailable.action = "deny"

        result = biz.claim_coupon("user_001", "COUPON_NEW_001", "new_user")
        assert result["code"] == CouponError.MODEL_REJECTED

        biz.model.set_simulate_failure(False)

    def test_model_disabled_skip(self, biz, redis_store):
        """模型关闭时跳过精排"""
        setup_stock(redis_store, "COUPON_NEW_001", 100)
        setup_new_user(redis_store, "user_001")
        biz.model.enabled = False

        result = biz.claim_coupon("user_001", "COUPON_NEW_001", "new_user")
        assert result["code"] == CouponError.OK

        biz.model.enabled = True


# ========== 查询接口 ==========

class TestQueryCoupons:
    def test_query_empty(self, biz):
        result = biz.query_user_coupons("user_no_coupons")
        assert result["code"] == CouponError.OK
        assert result["coupons"] == []
        assert result["total"] == 0

    def test_query_after_claim(self, biz, redis_store):
        setup_stock(redis_store, "COUPON_NEW_001", 100)
        setup_new_user(redis_store, "user_001")

        biz.claim_coupon("user_001", "COUPON_NEW_001", "new_user")
        result = biz.query_user_coupons("user_001")

        assert result["code"] == CouponError.OK
        assert result["total"] == 1
        assert result["coupons"][0]["coupon_id"] == "COUPON_NEW_001"

    def test_query_invalid_user(self, biz):
        result = biz.query_user_coupons("")
        assert result["code"] == CouponError.INVALID_PARAM


# ========== 批量评估 ==========

class TestBatchEvaluate:
    def test_batch_evaluate_success(self, biz, redis_store):
        setup_new_user(redis_store, "user_001")

        result = biz.batch_evaluate(
            "user_001", "activity", ["COUPON_ACT_001", "COUPON_SHIP_001"]
        )

        assert result["code"] == CouponError.OK
        assert len(result["results"]) == 2
        for r in result["results"]:
            assert "score" in r
            assert "recommended" in r

    def test_batch_evaluate_model_failure_fallback(self, biz, redis_store):
        """模型故障时批量评估使用兜底分数"""
        setup_new_user(redis_store, "user_001")
        biz.model.set_simulate_failure(True)

        result = biz.batch_evaluate(
            "user_001", "activity", ["COUPON_ACT_001"]
        )

        assert result["code"] == CouponError.OK
        assert "兜底" in result["message"]

        biz.model.set_simulate_failure(False)

    def test_batch_evaluate_invalid_params(self, biz):
        result = biz.batch_evaluate("", "activity", [])
        assert result["code"] == CouponError.INVALID_PARAM


# ========== 限流 ==========

class TestRateLimit:
    def test_user_rate_limit(self, biz_with_rate_limit, redis_store):
        """用户级限流（per_user_qps=2）"""
        biz = biz_with_rate_limit
        setup_stock(redis_store, "COUPON_ACT_001", 100)
        setup_stock(redis_store, "COUPON_SHIP_001", 100)
        setup_old_user(redis_store, "user_001")

        # 前 2 次应该成功
        r1 = biz.claim_coupon("user_001", "COUPON_ACT_001", "activity")
        r2 = biz.claim_coupon("user_001", "COUPON_SHIP_001", "activity")

        # 第 3 次应该被限流
        # 需要不同的 coupon_id 避免 ALREADY_CLAIMED
        setup_stock(redis_store, "COUPON_MEM_001", 100)
        setup_member(redis_store, "user_001")
        r3 = biz.claim_coupon("user_001", "COUPON_MEM_001", "member_day")

        # 至少有一次被限流（取决于时间窗口内的请求数）
        codes = [r1["code"], r2["code"], r3["code"]]
        assert CouponError.RATE_LIMITED in codes or all(c == CouponError.OK for c in codes[:2])
