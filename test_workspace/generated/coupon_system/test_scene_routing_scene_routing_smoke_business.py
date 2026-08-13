# Auto-generated from test_workspace/suites/coupon_system/scene_routing_smoke/business.md
# DO NOT EDIT — regenerate with: aitest codegen --suite-file test_workspace/suites/coupon_system/scene_routing_smoke/suite.yaml
import pytest
from test_workspace.targets.coupon_system.helpers import http as http_helper
from aitest_kit.helpers.request_binding import build_request
from aitest_kit.runtime_context import reset_case_context, set_case_context
pytest_plugins = ["test_workspace.targets.coupon_system.modules.scene_routing.fixture"]


BASE_REQUEST = {
    "user_id": None,
    "scene_name": "game",
    "device": "mobile",
    "policy_id": "",
    "external": 0,
    "reqId": None,
    "score_threshold": 0.0,
    "max_claim_per_request": 1,
    "context": {},
    "items": [{"item_id": "COUPON_ROUTE_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}],
}


def _req(*, auto_fields=None, overrides=None, patches=None) -> dict:
    return build_request(
        BASE_REQUEST,
        auto_fields=auto_fields or {},
        overrides=overrides or {},
        patches=patches or [],
    )


class TestSceneRoutingBusiness:
    """scene_routing 业务测试用例"""

    # ── 一、基础路由 ──

    def test_tc_route_001(self, setup_scene_routing):
        """TC-ROUTE-001：HTTP game/mobile 路由到 scene_id=1001"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-001",
            "module": "scene_routing",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/scene_routing_smoke/business.md",
            "title": "HTTP game/mobile 路由到 scene_id=1001",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 请求覆盖：HTTP 请求 user_id="u_route_game_mobile"、scene_name="game"、device="mobile"、policy_id=""、external=0

            harness = setup_scene_routing
            harness.prepare_stock(coupon_id="COUPON_ROUTE_001")
            resp = harness.recommend_http(request_overrides={"user_id": "u_route_game_mobile", "reqId": "req-route-001", "scene_name": "game", "device": "mobile", "policy_id": "", "external": 0})
            assert resp["code"] == 0
            assert resp["scene_id"] == 1001
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_route_002(self, setup_scene_routing):
        """TC-ROUTE-002：gRPC ad/pc 路由到 scene_id=2002"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-002",
            "module": "scene_routing",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/scene_routing_smoke/business.md",
            "title": "gRPC ad/pc 路由到 scene_id=2002",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：gRPC
            # SETUP: 请求覆盖：gRPC 请求 user_id="u_route_ad_pc"、scene_name="ad"、device="pc"、policy_id=""、external=0

            harness = setup_scene_routing
            harness.prepare_stock(coupon_id="COUPON_ROUTE_001")
            resp = harness.recommend_grpc(request_overrides={"user_id": "u_route_ad_pc", "req_id": "req-route-002", "scene_name": "ad", "device": "pc", "policy_id": "", "external": 0})
            assert resp["code"] == 0
            assert resp["scene_id"] == 2002
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_route_003(self, setup_scene_routing):
        """TC-ROUTE-003：external=1 时场景路由正常计算"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-003",
            "module": "scene_routing",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/scene_routing_smoke/business.md",
            "title": "external=1 时场景路由正常计算",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 请求覆盖：HTTP 请求 user_id="u_route_external"、scene_name="game"、device="mobile"、policy_id=""、external=1

            harness = setup_scene_routing
            harness.prepare_stock(coupon_id="COUPON_ROUTE_001")
            resp = harness.recommend_http(request_overrides={"user_id": "u_route_external", "reqId": "req-route-003", "scene_name": "game", "device": "mobile", "policy_id": "", "external": 1})
            assert resp["code"] == 0
            assert resp["scene_id"] == 1001
        finally:
            reset_case_context(__aitest_ctx_token)

    # ── 二、兜底策略 ──

    def test_tc_route_004(self, setup_scene_routing):
        """TC-ROUTE-004：policy_id 命中兜底时跳过实验和打分"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-004",
            "module": "scene_routing",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/scene_routing_smoke/business.md",
            "title": "policy_id 命中兜底时跳过实验和打分",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 请求覆盖：HTTP 请求 user_id="u_route_policy_fb"、scene_name="game"、device="mobile"、policy_id="policy_fallback_001"、external=0

            harness = setup_scene_routing
            harness.prepare_stock(coupon_id="COUPON_ROUTE_001")
            resp = harness.recommend_http(request_overrides={"user_id": "u_route_policy_fb", "reqId": "req-route-004", "scene_name": "game", "device": "mobile", "policy_id": "policy_fallback_001", "external": 0})
            assert resp["code"] == 0
            assert resp["scene_id"] == 3001
            assert resp["experiment_info"] == {}
            assert resp["results"][0]["score"] == resp["results"][0]["calibrated_score"]
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_route_005(self, setup_scene_routing):
        """TC-ROUTE-005：兜底发放时 user_id 正确传递"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-005",
            "module": "scene_routing",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/scene_routing_smoke/business.md",
            "title": "兜底发放时 user_id 正确传递",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 请求覆盖：HTTP 请求 user_id="u_fallback"、scene_name="game"、device="mobile"、policy_id="policy_fallback_001"、external=0、score_threshold=0.0

            harness = setup_scene_routing
            harness.prepare_stock(coupon_id="COUPON_ROUTE_001")
            resp = harness.recommend_http(request_overrides={"user_id": "u_fallback", "reqId": "req-route-005", "scene_name": "game", "device": "mobile", "policy_id": "policy_fallback_001", "external": 0, "score_threshold": 0.0})
            assert resp["code"] == 0
            assert resp["coupon"] is not None
            assert resp["coupon"]["user_id"] == "u_fallback"
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_route_006(self, setup_scene_routing):
        """TC-ROUTE-006：未知场景组合走兜底场景"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-006",
            "module": "scene_routing",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/scene_routing_smoke/business.md",
            "title": "未知场景组合走兜底场景",
            "priority": "P1 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：gRPC
            # SETUP: 请求覆盖：gRPC 请求 user_id="u_route_unknown"、scene_name="unknown_scene"、device="unknown_device"、policy_id=""、external=0

            harness = setup_scene_routing
            harness.prepare_stock(coupon_id="COUPON_ROUTE_001")
            resp = harness.recommend_grpc(request_overrides={"user_id": "u_route_unknown", "req_id": "req-route-006", "scene_name": "unknown_scene", "device": "unknown_device", "policy_id": "", "external": 0})
            assert resp["code"] == 0
            assert resp["scene_id"] == 3001
            assert resp["experiment_info"] == {}
        finally:
            reset_case_context(__aitest_ctx_token)

    # ── 三、兜底分三级读取 ──

    def test_tc_route_007(self, setup_scene_routing):
        """TC-ROUTE-007：优先使用 Redis 场景级兜底分"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-007",
            "module": "scene_routing",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/scene_routing_smoke/business.md",
            "title": "优先使用 Redis 场景级兜底分",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 前置操作：执行 SET coupon:fallback:score:3001 0.8 和 SET coupon:fallback:score:default 0.6
            # SETUP: 请求覆盖：HTTP 请求命中 policy_fallback_001

            harness = setup_scene_routing
            harness.set_fallback_scores({"coupon:fallback:score:3001": "0.8", "coupon:fallback:score:default": "0.6"})
            harness.prepare_stock(coupon_id="COUPON_ROUTE_001")
            resp = harness.recommend_http(request_overrides={"user_id": "u_route_007", "reqId": "req-route-007", "scene_name": "game", "device": "mobile", "policy_id": "policy_fallback_001", "external": 0})
            assert resp["code"] == 0
            assert resp["results"][0]["score"] == 0.8
            assert resp["results"][0]["calibrated_score"] == 0.8
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_route_008(self, setup_scene_routing):
        """TC-ROUTE-008：场景级不存在时使用 Redis 全局兜底分"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-008",
            "module": "scene_routing",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/scene_routing_smoke/business.md",
            "title": "场景级不存在时使用 Redis 全局兜底分",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 前置操作：执行 DEL coupon:fallback:score:3001 和 SET coupon:fallback:score:default 0.6
            # SETUP: 请求覆盖：HTTP 请求命中 policy_fallback_001

            harness = setup_scene_routing
            harness.set_fallback_scores({"coupon:fallback:score:default": "0.6"})
            harness.prepare_stock(coupon_id="COUPON_ROUTE_001")
            resp = harness.recommend_http(request_overrides={"user_id": "u_route_008", "reqId": "req-route-008", "scene_name": "game", "device": "mobile", "policy_id": "policy_fallback_001", "external": 0})
            assert resp["code"] == 0
            assert resp["results"][0]["score"] == 0.6
            assert resp["results"][0]["calibrated_score"] == 0.6
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_route_009(self, setup_scene_routing):
        """TC-ROUTE-009：Redis 兜底分都不存在时使用配置默认值"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-009",
            "module": "scene_routing",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/scene_routing_smoke/business.md",
            "title": "Redis 兜底分都不存在时使用配置默认值",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 前置操作：执行 DEL coupon:fallback:score:3001 coupon:fallback:score:default
            # SETUP: 请求覆盖：HTTP 请求命中 policy_fallback_001

            harness = setup_scene_routing
            harness.clear_fallback_scores()
            harness.prepare_stock(coupon_id="COUPON_ROUTE_001")
            resp = harness.recommend_http(request_overrides={"user_id": "u_route_009", "reqId": "req-route-009", "scene_name": "game", "device": "mobile", "policy_id": "policy_fallback_001", "external": 0})
            assert resp["code"] == 0
            assert resp["results"][0]["score"] == 0.5
            assert resp["results"][0]["calibrated_score"] == 0.5
        finally:
            reset_case_context(__aitest_ctx_token)



__codegen_skipped__ = []
