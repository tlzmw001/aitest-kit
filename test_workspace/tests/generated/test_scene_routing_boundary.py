# Auto-generated from test_workspace/cases/scene_routing/boundary.md
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
    "items": [{"item_id": "COUPON_ROUTE_BOUNDARY_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}],
}


def _req(user_id: str, req_id: str, **overrides) -> dict:
    body = {**BASE_REQUEST, "user_id": user_id, "reqId": req_id}
    body.update(overrides)
    return body


class TestSceneRoutingBoundary:
    """scene_routing 边界测试用例"""

    # ── 一、兜底分容错 ──

    def test_tc_route_011(self, http_base_url, setup_scene_routing):
        """TC-ROUTE-011：Redis 全局兜底分非数字时回退到配置默认值"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-011",
            "module": "scene_routing",
            "category": "boundary",
            "source": "test_workspace/cases/scene_routing/boundary.md",
            "title": "Redis 全局兜底分非数字时回退到配置默认值",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 前置操作：执行 DEL coupon:fallback:score:3001 和 SET coupon:fallback:score:default not-a-number
        # SETUP: 请求覆盖：HTTP 请求命中 policy_fallback_001
        setup_scene_routing(case_id="TC-ROUTE-011")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_route_011", "req_route_011", **{"scene_name": "game", "device": "mobile", "policy_id": "policy_fallback_001", "external": 0}))
        assert resp["code"] == 0
        assert resp["scene_id"] == 3001
        assert resp["results"][0]["score"] == 0.5

    # ── 二、路由匹配边界 ──

    def test_tc_route_013(self, http_base_url, setup_scene_routing):
        """TC-ROUTE-013：policy_id 为空字符串时不触发兜底策略"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-013",
            "module": "scene_routing",
            "category": "boundary",
            "source": "test_workspace/cases/scene_routing/boundary.md",
            "title": "policy_id 为空字符串时不触发兜底策略",
            "priority": "P2",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 scene_name="game"、device="mobile"、policy_id=""
        setup_scene_routing(case_id="TC-ROUTE-013")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_route_013", "req_route_013", **{"scene_name": "game", "device": "mobile", "policy_id": "", "external": 0}))
        assert resp["code"] == 0
        assert resp["scene_id"] == 1001

    def test_tc_route_014(self, grpc_target, setup_scene_routing):
        """TC-ROUTE-014：scene_name 大小写不同视为未匹配并走兜底"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-014",
            "module": "scene_routing",
            "category": "boundary",
            "source": "test_workspace/cases/scene_routing/boundary.md",
            "title": "scene_name 大小写不同视为未匹配并走兜底",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 请求覆盖：gRPC 请求 scene_name="Game"、device="mobile"、policy_id=""
        setup_scene_routing(case_id="TC-ROUTE-014")

        resp = grpc_ops.recommend(grpc_target, _req("u_route_014", "req_route_014", **{"scene_name": "Game", "device": "mobile", "policy_id": "", "external": 0}))
        assert resp["code"] == 0
        assert resp["scene_id"] == 3001
        assert resp["experiment_info"] == {}

    # ── 三、配置生命周期 ──

    def test_tc_route_018(self, grpc_target, setup_scene_routing):
        """TC-ROUTE-018：gRPC policy_id 为空字符串时不触发兜底策略"""
        __tc_meta__ = {
            "tc_id": "TC-ROUTE-018",
            "module": "scene_routing",
            "category": "boundary",
            "source": "test_workspace/cases/scene_routing/boundary.md",
            "title": "gRPC policy_id 为空字符串时不触发兜底策略",
            "priority": "P2",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 请求覆盖：gRPC 请求 scene_name="game"、device="mobile"、policy_id=""
        setup_scene_routing(case_id="TC-ROUTE-018")

        resp = grpc_ops.recommend(grpc_target, _req("u_route_018", "req_route_018", **{"scene_name": "game", "device": "mobile", "policy_id": "", "external": 0}))
        assert resp["code"] == 0
        assert resp["scene_id"] == 1001


# SKIPPED: TC-ROUTE-010 — `[!可行性存疑: 待测系统当前未按规格在场景级兜底分非数字时继续读取全局兜底分，已记录到 results/scene_routing_fallback_invalid_scene_score_bug.md]`
# SKIPPED: TC-ROUTE-012 — `[!可行性存疑: 需要测试环境允许控制 Redis 可用性]`
# SKIPPED: TC-ROUTE-015 — `[!可行性存疑: 需要测试环境支持独立路由配置启动服务]`
# SKIPPED: TC-ROUTE-016 — `[!可行性存疑: 该行为依赖独立测试配置，不应修改仓库默认配置]`
# SKIPPED: TC-ROUTE-017 — `[!可行性存疑: 待测系统当前未按规格在场景级兜底分非数字时继续读取全局兜底分，已记录到 results/scene_routing_fallback_invalid_scene_score_bug.md]`
# SKIPPED: TC-ROUTE-019 — `[!可行性存疑: 需要测试环境支持独立路由配置启动服务]`

__codegen_skipped__ = [{"tc_id": "TC-ROUTE-010", "module": "scene_routing", "category": "boundary", "source": "test_workspace/cases/scene_routing/boundary.md", "title": "Redis 场景级兜底分非数字时回退到全局兜底分", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 待测系统当前未按规格在场景级兜底分非数字时继续读取全局兜底分，已记录到 results/scene_routing_fallback_invalid_scene_score_bug.md]`"], "reason": "`[!可行性存疑: 待测系统当前未按规格在场景级兜底分非数字时继续读取全局兜底分，已记录到 results/scene_routing_fallback_invalid_scene_score_bug.md]`"}, {"tc_id": "TC-ROUTE-012", "module": "scene_routing", "category": "boundary", "source": "test_workspace/cases/scene_routing/boundary.md", "title": "兜底分 Redis 读取异常时请求失败", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 需要测试环境允许控制 Redis 可用性]`"], "reason": "`[!可行性存疑: 需要测试环境允许控制 Redis 可用性]`"}, {"tc_id": "TC-ROUTE-015", "module": "scene_routing", "category": "boundary", "source": "test_workspace/cases/scene_routing/boundary.md", "title": "路由表为空时所有非 policy 兜底请求走兜底场景", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 需要测试环境支持独立路由配置启动服务]`"], "reason": "`[!可行性存疑: 需要测试环境支持独立路由配置启动服务]`"}, {"tc_id": "TC-ROUTE-016", "module": "scene_routing", "category": "boundary", "source": "test_workspace/cases/scene_routing/boundary.md", "title": "运行中修改路由配置不会热更新", "priority": "P2", "markers": ["`[!可行性存疑: 该行为依赖独立测试配置，不应修改仓库默认配置]`"], "reason": "`[!可行性存疑: 该行为依赖独立测试配置，不应修改仓库默认配置]`"}, {"tc_id": "TC-ROUTE-017", "module": "scene_routing", "category": "boundary", "source": "test_workspace/cases/scene_routing/boundary.md", "title": "gRPC Redis 场景级兜底分非数字时回退到全局兜底分", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 待测系统当前未按规格在场景级兜底分非数字时继续读取全局兜底分，已记录到 results/scene_routing_fallback_invalid_scene_score_bug.md]`"], "reason": "`[!可行性存疑: 待测系统当前未按规格在场景级兜底分非数字时继续读取全局兜底分，已记录到 results/scene_routing_fallback_invalid_scene_score_bug.md]`"}, {"tc_id": "TC-ROUTE-019", "module": "scene_routing", "category": "boundary", "source": "test_workspace/cases/scene_routing/boundary.md", "title": "gRPC 路由表为空时所有非 policy 兜底请求走兜底场景", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 需要测试环境支持独立路由配置启动服务]`"], "reason": "`[!可行性存疑: 需要测试环境支持独立路由配置启动服务]`"}]
