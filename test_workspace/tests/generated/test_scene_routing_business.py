# Auto-generated from test_workspace/cases/scene_routing/business.md
# DO NOT EDIT — regenerate with: /test-codegen scene_routing
import pytest
from test_workspace.tests.helpers import http as http_helper
from test_workspace.tests.helpers import grpc_ops


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


def _req(user_id: str, req_id: str, **overrides) -> dict:
    body = {**BASE_REQUEST, "user_id": user_id, "reqId": req_id}
    body.update(overrides)
    return body


class TestSceneRoutingBusiness:
    """scene_routing 业务测试用例"""

    # ── 一、基础路由 ──

    def test_tc_route_001(self, http_base_url, setup_scene_routing):
        """TC-ROUTE-001：HTTP game/mobile 路由到 scene_id=1001"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-001",
            "module": "scene_routing",
            "category": "business",
            "source": "test_workspace/cases/scene_routing/business.md",
            "title": "HTTP game/mobile 路由到 scene_id=1001",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_route_game_mobile"、scene_name="game"、device="mobile"、policy_id=""、external=0
        setup_scene_routing(case_id="TC-ROUTE-001")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_route_game_mobile", "req_route_001", **{"scene_name": "game", "device": "mobile", "policy_id": "", "external": 0}))
        assert resp["code"] == 0
        assert resp["scene_id"] == 1001

    def test_tc_route_002(self, grpc_target, setup_scene_routing):
        """TC-ROUTE-002：gRPC ad/pc 路由到 scene_id=2002"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-002",
            "module": "scene_routing",
            "category": "business",
            "source": "test_workspace/cases/scene_routing/business.md",
            "title": "gRPC ad/pc 路由到 scene_id=2002",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 请求覆盖：gRPC 请求 user_id="u_route_ad_pc"、scene_name="ad"、device="pc"、policy_id=""、external=0
        setup_scene_routing(case_id="TC-ROUTE-002")

        resp = grpc_ops.recommend(grpc_target, _req("u_route_ad_pc", "req_route_002", **{"scene_name": "ad", "device": "pc", "policy_id": "", "external": 0}))
        assert resp["code"] == 0
        assert resp["scene_id"] == 2002

    def test_tc_route_003(self, http_base_url, setup_scene_routing):
        """TC-ROUTE-003：external=1 时场景路由正常计算"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-003",
            "module": "scene_routing",
            "category": "business",
            "source": "test_workspace/cases/scene_routing/business.md",
            "title": "external=1 时场景路由正常计算",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_route_external"、scene_name="game"、device="mobile"、policy_id=""、external=1
        setup_scene_routing(case_id="TC-ROUTE-003")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_route_external", "req_route_003", **{"scene_name": "game", "device": "mobile", "policy_id": "", "external": 1}))
        assert resp["code"] == 0
        assert resp["scene_id"] == 1001

    # ── 二、兜底策略 ──

    def test_tc_route_004(self, http_base_url, setup_scene_routing):
        """TC-ROUTE-004：policy_id 命中兜底时跳过实验和打分"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-004",
            "module": "scene_routing",
            "category": "business",
            "source": "test_workspace/cases/scene_routing/business.md",
            "title": "policy_id 命中兜底时跳过实验和打分",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_route_policy_fb"、scene_name="game"、device="mobile"、policy_id="policy_fallback_001"、external=0
        setup_scene_routing(case_id="TC-ROUTE-004")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_route_policy_fb", "req_route_004", **{"scene_name": "game", "device": "mobile", "policy_id": "policy_fallback_001", "external": 0}))
        assert resp["code"] == 0
        cal = resp["results"][0]["calibrated_score"]
        assert resp["scene_id"] == 3001
        assert resp["experiment_info"] == {}
        assert resp["results"][0]["score"] == resp["results"][0]["calibrated_score"]

    def test_tc_route_005(self, http_base_url, setup_scene_routing):
        """TC-ROUTE-005：兜底发放时 user_id 正确传递"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-005",
            "module": "scene_routing",
            "category": "business",
            "source": "test_workspace/cases/scene_routing/business.md",
            "title": "兜底发放时 user_id 正确传递",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_fallback"、scene_name="game"、device="mobile"、policy_id="policy_fallback_001"、external=0、score_threshold=0.0
        setup_scene_routing(case_id="TC-ROUTE-005")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_fallback", "req_route_005", **{"scene_name": "game", "device": "mobile", "policy_id": "policy_fallback_001", "external": 0, "score_threshold": 0.0}))
        assert resp["code"] == 0
        assert resp["coupon"] is not None
        assert resp["coupon"]["user_id"] == "u_fallback"

    def test_tc_route_006(self, grpc_target, setup_scene_routing):
        """TC-ROUTE-006：未知场景组合走兜底场景"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-006",
            "module": "scene_routing",
            "category": "business",
            "source": "test_workspace/cases/scene_routing/business.md",
            "title": "未知场景组合走兜底场景",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 请求覆盖：gRPC 请求 user_id="u_route_unknown"、scene_name="unknown_scene"、device="unknown_device"、policy_id=""、external=0
        setup_scene_routing(case_id="TC-ROUTE-006")

        resp = grpc_ops.recommend(grpc_target, _req("u_route_unknown", "req_route_006", **{"scene_name": "unknown_scene", "device": "unknown_device", "policy_id": "", "external": 0}))
        assert resp["code"] == 0
        assert resp["scene_id"] == 3001
        assert resp["experiment_info"] == {}

    # ── 三、兜底分三级读取 ──

    def test_tc_route_007(self, http_base_url, setup_scene_routing):
        """TC-ROUTE-007：优先使用 Redis 场景级兜底分"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-007",
            "module": "scene_routing",
            "category": "business",
            "source": "test_workspace/cases/scene_routing/business.md",
            "title": "优先使用 Redis 场景级兜底分",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 前置操作：执行 SET coupon:fallback:score:3001 0.8 和 SET coupon:fallback:score:default 0.6
        # SETUP: 请求覆盖：HTTP 请求命中 policy_fallback_001
        setup_scene_routing(case_id="TC-ROUTE-007")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_route_007", "req_route_007", **{"scene_name": "game", "device": "mobile", "policy_id": "policy_fallback_001", "external": 0}))
        assert resp["code"] == 0
        cal = resp["results"][0]["calibrated_score"]
        assert resp["results"][0]["score"] == 0.8
        assert resp["results"][0]["calibrated_score"] == 0.8

    def test_tc_route_008(self, http_base_url, setup_scene_routing):
        """TC-ROUTE-008：场景级不存在时使用 Redis 全局兜底分"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-008",
            "module": "scene_routing",
            "category": "business",
            "source": "test_workspace/cases/scene_routing/business.md",
            "title": "场景级不存在时使用 Redis 全局兜底分",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 前置操作：执行 DEL coupon:fallback:score:3001 和 SET coupon:fallback:score:default 0.6
        # SETUP: 请求覆盖：HTTP 请求命中 policy_fallback_001
        setup_scene_routing(case_id="TC-ROUTE-008")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_route_008", "req_route_008", **{"scene_name": "game", "device": "mobile", "policy_id": "policy_fallback_001", "external": 0}))
        assert resp["code"] == 0
        cal = resp["results"][0]["calibrated_score"]
        assert resp["results"][0]["score"] == 0.6
        assert resp["results"][0]["calibrated_score"] == 0.6

    def test_tc_route_009(self, http_base_url, setup_scene_routing):
        """TC-ROUTE-009：Redis 兜底分都不存在时使用配置默认值"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-009",
            "module": "scene_routing",
            "category": "business",
            "source": "test_workspace/cases/scene_routing/business.md",
            "title": "Redis 兜底分都不存在时使用配置默认值",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 前置操作：执行 DEL coupon:fallback:score:3001 coupon:fallback:score:default
        # SETUP: 请求覆盖：HTTP 请求命中 policy_fallback_001
        setup_scene_routing(case_id="TC-ROUTE-009")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_route_009", "req_route_009", **{"scene_name": "game", "device": "mobile", "policy_id": "policy_fallback_001", "external": 0}))
        assert resp["code"] == 0
        cal = resp["results"][0]["calibrated_score"]
        assert resp["results"][0]["score"] == 0.5
        assert resp["results"][0]["calibrated_score"] == 0.5



__codegen_skipped__ = []
