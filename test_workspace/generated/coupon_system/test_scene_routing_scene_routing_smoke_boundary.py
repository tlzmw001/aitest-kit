# Auto-generated from test_workspace/suites/coupon_system/scene_routing_smoke/boundary.md
# DO NOT EDIT — regenerate with: aitest codegen --suite-file test_workspace/suites/coupon_system/scene_routing_smoke/suite.yaml
import pytest
from test_workspace.targets.coupon_system.helpers import http as http_helper
from aitest_kit.helpers.request_binding import build_request
from aitest_kit.runtime_context import reset_case_context, set_case_context
from test_workspace.targets.coupon_system.fixtures.scene_routing import setup_scene_routing


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
    "items": [{"item_id": "COUPON_ROUTE_BOUNDARY_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}],
}


def _req(*, auto_fields=None, overrides=None, patches=None) -> dict:
    return build_request(
        BASE_REQUEST,
        auto_fields=auto_fields or {},
        overrides=overrides or {},
        patches=patches or [],
    )


class TestSceneRoutingBoundary:
    """scene_routing 边界测试用例"""

    # ── 一、兜底分容错 ──

    def test_tc_route_011(self, setup_scene_routing):
        """TC-ROUTE-011：Redis 全局兜底分非数字时回退到配置默认值"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-011",
            "module": "scene_routing",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/scene_routing_smoke/boundary.md",
            "title": "Redis 全局兜底分非数字时回退到配置默认值",
            "priority": "P2 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 前置操作：执行 DEL coupon:fallback:score:3001 和 SET coupon:fallback:score:default not-a-number
            # SETUP: 请求覆盖：HTTP 请求命中 policy_fallback_001

            client = setup_scene_routing
            client.set_fallback_scores({"coupon:fallback:score:default": "not-a-number"})
            client.prepare_stock(coupon_id="COUPON_ROUTE_BOUNDARY_001")
            resp = client.recommend_http(request_overrides={"user_id": "u_route_011", "reqId": "req-route-011", "scene_name": "game", "device": "mobile", "policy_id": "policy_fallback_001", "external": 0, "items": [{"item_id": "COUPON_ROUTE_BOUNDARY_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}]})
            assert resp["code"] == 0
            assert resp["scene_id"] == 3001
            assert resp["results"][0]["score"] == 0.5
        finally:
            reset_case_context(__aitest_ctx_token)

    # ── 二、路由匹配边界 ──

    def test_tc_route_013(self, setup_scene_routing):
        """TC-ROUTE-013：policy_id 为空字符串时不触发兜底策略"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-013",
            "module": "scene_routing",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/scene_routing_smoke/boundary.md",
            "title": "policy_id 为空字符串时不触发兜底策略",
            "priority": "P2",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 请求覆盖：HTTP 请求 scene_name="game"、device="mobile"、policy_id=""

            client = setup_scene_routing
            client.prepare_stock(coupon_id="COUPON_ROUTE_BOUNDARY_001")
            resp = client.recommend_http(request_overrides={"user_id": "u_route_013", "reqId": "req-route-013", "scene_name": "game", "device": "mobile", "policy_id": "", "external": 0, "items": [{"item_id": "COUPON_ROUTE_BOUNDARY_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}]})
            assert resp["code"] == 0
            assert resp["scene_id"] == 1001
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_route_014(self, setup_scene_routing):
        """TC-ROUTE-014：scene_name 大小写不同视为未匹配并走兜底"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-014",
            "module": "scene_routing",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/scene_routing_smoke/boundary.md",
            "title": "scene_name 大小写不同视为未匹配并走兜底",
            "priority": "P2 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：gRPC
            # SETUP: 请求覆盖：gRPC 请求 scene_name="Game"、device="mobile"、policy_id=""

            client = setup_scene_routing
            client.prepare_stock(coupon_id="COUPON_ROUTE_BOUNDARY_001")
            resp = client.recommend_grpc(request_overrides={"user_id": "u_route_014", "req_id": "req-route-014", "scene_name": "Game", "device": "mobile", "policy_id": "", "external": 0, "items": [{"item_id": "COUPON_ROUTE_BOUNDARY_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}]})
            assert resp["code"] == 0
            assert resp["scene_id"] == 3001
            assert resp["experiment_info"] == {}
        finally:
            reset_case_context(__aitest_ctx_token)

    # ── 三、配置生命周期 ──

    def test_tc_route_018(self, setup_scene_routing):
        """TC-ROUTE-018：gRPC policy_id 为空字符串时不触发兜底策略"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-018",
            "module": "scene_routing",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/scene_routing_smoke/boundary.md",
            "title": "gRPC policy_id 为空字符串时不触发兜底策略",
            "priority": "P2",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：gRPC
            # SETUP: 请求覆盖：gRPC 请求 scene_name="game"、device="mobile"、policy_id=""

            client = setup_scene_routing
            client.prepare_stock(coupon_id="COUPON_ROUTE_BOUNDARY_001")
            resp = client.recommend_grpc(request_overrides={"user_id": "u_route_018", "req_id": "req-route-018", "scene_name": "game", "device": "mobile", "policy_id": "", "external": 0, "items": [{"item_id": "COUPON_ROUTE_BOUNDARY_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}]})
            assert resp["code"] == 0
            assert resp["scene_id"] == 1001
        finally:
            reset_case_context(__aitest_ctx_token)


# TODO: setup_scene_routing fixture 需要手写实现（→ tests/fixtures/scene_routing.py）
# SKIPPED: TC-ROUTE-010 — `[!可行性存疑: 待测系统当前未按规格在场景级兜底分非数字时继续读取全局兜底分，已记录到 results/scene_routing_fallback_invalid_scene_score_bug.md]`
# SKIPPED: TC-ROUTE-012 — `[!可行性存疑: 需要测试环境允许控制 Redis 可用性]`
# SKIPPED: TC-ROUTE-015 — `[!可行性存疑: 需要测试环境支持独立路由配置启动服务]`
# SKIPPED: TC-ROUTE-016 — `[!可行性存疑: 该行为依赖独立测试配置，不应修改仓库默认配置]`
# SKIPPED: TC-ROUTE-017 — `[!可行性存疑: 待测系统当前未按规格在场景级兜底分非数字时继续读取全局兜底分，已记录到 results/scene_routing_fallback_invalid_scene_score_bug.md]`
# SKIPPED: TC-ROUTE-019 — `[!可行性存疑: 需要测试环境支持独立路由配置启动服务]`

__codegen_skipped__ = [{"tc_id": "TC-ROUTE-010", "module": "scene_routing", "category": "boundary", "source": "test_workspace/suites/coupon_system/scene_routing_smoke/boundary.md", "title": "Redis 场景级兜底分非数字时回退到全局兜底分", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 待测系统当前未按规格在场景级兜底分非数字时继续读取全局兜底分，已记录到 results/scene_routing_fallback_invalid_scene_score_bug.md]`"], "reason": "`[!可行性存疑: 待测系统当前未按规格在场景级兜底分非数字时继续读取全局兜底分，已记录到 results/scene_routing_fallback_invalid_scene_score_bug.md]`"}, {"tc_id": "TC-ROUTE-012", "module": "scene_routing", "category": "boundary", "source": "test_workspace/suites/coupon_system/scene_routing_smoke/boundary.md", "title": "兜底分 Redis 读取异常时请求失败", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 需要测试环境允许控制 Redis 可用性]`"], "reason": "`[!可行性存疑: 需要测试环境允许控制 Redis 可用性]`"}, {"tc_id": "TC-ROUTE-015", "module": "scene_routing", "category": "boundary", "source": "test_workspace/suites/coupon_system/scene_routing_smoke/boundary.md", "title": "路由表为空时所有非 policy 兜底请求走兜底场景", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 需要测试环境支持独立路由配置启动服务]`"], "reason": "`[!可行性存疑: 需要测试环境支持独立路由配置启动服务]`"}, {"tc_id": "TC-ROUTE-016", "module": "scene_routing", "category": "boundary", "source": "test_workspace/suites/coupon_system/scene_routing_smoke/boundary.md", "title": "运行中修改路由配置不会热更新", "priority": "P2", "markers": ["`[!可行性存疑: 该行为依赖独立测试配置，不应修改仓库默认配置]`"], "reason": "`[!可行性存疑: 该行为依赖独立测试配置，不应修改仓库默认配置]`"}, {"tc_id": "TC-ROUTE-017", "module": "scene_routing", "category": "boundary", "source": "test_workspace/suites/coupon_system/scene_routing_smoke/boundary.md", "title": "gRPC Redis 场景级兜底分非数字时回退到全局兜底分", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 待测系统当前未按规格在场景级兜底分非数字时继续读取全局兜底分，已记录到 results/scene_routing_fallback_invalid_scene_score_bug.md]`"], "reason": "`[!可行性存疑: 待测系统当前未按规格在场景级兜底分非数字时继续读取全局兜底分，已记录到 results/scene_routing_fallback_invalid_scene_score_bug.md]`"}, {"tc_id": "TC-ROUTE-019", "module": "scene_routing", "category": "boundary", "source": "test_workspace/suites/coupon_system/scene_routing_smoke/boundary.md", "title": "gRPC 路由表为空时所有非 policy 兜底请求走兜底场景", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 需要测试环境支持独立路由配置启动服务]`"], "reason": "`[!可行性存疑: 需要测试环境支持独立路由配置启动服务]`"}]
