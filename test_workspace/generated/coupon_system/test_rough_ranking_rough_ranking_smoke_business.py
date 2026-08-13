# Auto-generated from test_workspace/suites/coupon_system/rough_ranking_smoke/business.md
# DO NOT EDIT — regenerate with: aitest codegen --suite-file test_workspace/suites/coupon_system/rough_ranking_smoke/suite.yaml
import pytest
from test_workspace.targets.coupon_system.helpers import http as http_helper
from aitest_kit.helpers.request_binding import build_request
from aitest_kit.runtime_context import reset_case_context, set_case_context
pytest_plugins = ["test_workspace.targets.coupon_system.modules.rough_ranking.fixture"]


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
    "items": [{"item_id": "COUPON_RANK_A", "coupon_type": "discount", "value": 100, "min_spend": 9000, "expire_days": 7}, {"item_id": "COUPON_RANK_B", "coupon_type": "fixed", "value": 80, "min_spend": 1000, "expire_days": 7, "isPrior": True}, {"item_id": "COUPON_RANK_C", "coupon_type": "free_shipping", "value": 50, "min_spend": 500, "expire_days": 7}],
}


def _req(*, auto_fields=None, overrides=None, patches=None) -> dict:
    return build_request(
        BASE_REQUEST,
        auto_fields=auto_fields or {},
        overrides=overrides or {},
        patches=patches or [],
    )


class TestRoughRankingBusiness:
    """rough_ranking 业务测试用例"""

    # ── 一、实验控制 ──

    def test_tc_rank_001(self, setup_rough_ranking):
        """TC-RANK-001：HTTP 实验关闭时跳过粗排"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-001",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/business.md",
            "title": "HTTP 实验关闭时跳过粗排",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 前置操作：白名单命中粗排关闭策略 enable_coarse_rank=false
            # SETUP: 请求覆盖：HTTP 请求按 A,B,C 顺序传入 3 张券

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_001", request_id="req-rank-001", strategy_map={"coarse_rank_exp_game": "cr_off", "calibration_exp_game": "cal_off"}, params={"enable_coarse_rank": False})
            resp = harness.recommend_http()
            assert resp['code'] == 0
            assert harness.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B', 'COUPON_RANK_C']
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_rank_002(self, setup_rough_ranking):
        """TC-RANK-002：gRPC 实验开启且不配置增强能力时保持向后兼容"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-002",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/business.md",
            "title": "gRPC 实验开启且不配置增强能力时保持向后兼容",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：gRPC
            # SETUP: 策略参数：白名单命中{"enable_coarse_rank":true,"truncate_count":3}，不配置 prior_count、filters、sort_keys、diversity
            # SETUP: 请求覆盖：gRPC 请求按 A,B,C 顺序传入 3 张券

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_002", request_id="req-rank-002", params={"enable_coarse_rank": True, "truncate_count": 3})
            resp = harness.recommend_grpc()
            assert resp['code'] == 0
            assert harness.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B', 'COUPON_RANK_C']
        finally:
            reset_case_context(__aitest_ctx_token)

    # ── 二、基础截断 ──

    def test_tc_rank_003(self, setup_rough_ranking):
        """TC-RANK-003：top_value 按面额降序截断"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-003",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/business.md",
            "title": "top_value 按面额降序截断",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":2,"truncate_rule":"top_value"}
            # SETUP: 请求覆盖：HTTP 请求传入 A/B/C

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_003", request_id="req-rank-003", params={"enable_coarse_rank": True, "truncate_count": 2, "truncate_rule": "top_value"})
            resp = harness.recommend_http()
            assert resp['code'] == 0
            assert harness.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_rank_004(self, setup_rough_ranking):
        """TC-RANK-004：top_min_spend 按门槛降序截断"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-004",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/business.md",
            "title": "top_min_spend 按门槛降序截断",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":2,"truncate_rule":"top_min_spend"}
            # SETUP: 请求覆盖：HTTP 请求传入 A/B/C

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_004", request_id="req-rank-004", params={"enable_coarse_rank": True, "truncate_count": 2, "truncate_rule": "top_min_spend"})
            resp = harness.recommend_http()
            assert resp['code'] == 0
            assert harness.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_rank_005(self, setup_rough_ranking):
        """TC-RANK-005：random 截断只保证数量和来源"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-005",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/business.md",
            "title": "random 截断只保证数量和来源",
            "priority": "P2",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":2,"truncate_rule":"random"}
            # SETUP: 请求覆盖：HTTP 请求传入 A/B/C

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_005", request_id="req-rank-005", params={"enable_coarse_rank": True, "truncate_count": 2, "truncate_rule": "random"})
            resp = harness.recommend_http()
            assert resp['code'] == 0
            assert len(harness.rank_input_items) == 2
            assert set(harness.rank_input_items) <= {'COUPON_RANK_A', 'COUPON_RANK_B', 'COUPON_RANK_C'}
        finally:
            reset_case_context(__aitest_ctx_token)

    # ── 三、增强能力 ──

    def test_tc_rank_006(self, setup_rough_ranking):
        """TC-RANK-006：优先券保送后普通券补位"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-006",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/business.md",
            "title": "优先券保送后普通券补位",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":2,"prior_count":1,"prior_rule":"top_value","truncate_rule":"top_value"}
            # SETUP: 请求覆盖：B 为 isPrior=true

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_006", request_id="req-rank-006", params={"enable_coarse_rank": True, "truncate_count": 2, "prior_count": 1, "prior_rule": "top_value", "truncate_rule": "top_value"})
            resp = harness.recommend_http()
            assert resp['code'] == 0
            assert harness.rank_input_items[0] == 'COUPON_RANK_B'
            assert len(harness.rank_input_items) == 2
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_rank_007(self, setup_rough_ranking):
        """TC-RANK-007：多条件过滤取交集"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-007",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/business.md",
            "title": "多条件过滤取交集",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":3,"filters":[{"field":"value","op":"gte","value":80},{"field":"coupon_type","op":"in","value":["discount","fixed"]}]}

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_007", request_id="req-rank-007", params={"enable_coarse_rank": True, "truncate_count": 3, "filters": [{"field": "value", "op": "gte", "value": 80}, {"field": "coupon_type", "op": "in", "value": ["discount", "fixed"]}]})
            resp = harness.recommend_http()
            assert resp['code'] == 0
            assert harness.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_rank_008(self, setup_rough_ranking):
        """TC-RANK-008：多维排序按加权分排序"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-008",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/business.md",
            "title": "多维排序按加权分排序",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":3,"sort_keys":[{"field":"value","weight":1.0},{"field":"min_spend","weight":-1.0}]}

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_008", request_id="req-rank-008", params={"enable_coarse_rank": True, "truncate_count": 3, "sort_keys": [{"field": "value", "weight": 1.0}, {"field": "min_spend", "weight": -1.0}]})
            resp = harness.recommend_http()
            assert resp['code'] == 0
            assert harness.rank_input_items[0] == 'COUPON_RANK_B'
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_rank_009(self, setup_rough_ranking):
        """TC-RANK-009：类型打散限制同类型数量并回填"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-009",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/business.md",
            "title": "类型打散限制同类型数量并回填",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 请求覆盖：请求传入 4 张券，其中 3 张 coupon_type="discount"、1 张 coupon_type="fixed"
            # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":3,"truncate_rule":"top_value","diversity":{"enabled":true,"group_field":"coupon_type","max_per_group":1}}

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_009", request_id="req-rank-009", params={"enable_coarse_rank": True, "truncate_count": 3, "truncate_rule": "top_value", "diversity": {"enabled": True, "group_field": "coupon_type", "max_per_group": 1}}, items=[{"item_id": "COUPON_RANK_D1", "coupon_type": "discount", "value": 100, "min_spend": 1000, "expire_days": 7}, {"item_id": "COUPON_RANK_D2", "coupon_type": "discount", "value": 90, "min_spend": 1000, "expire_days": 7}, {"item_id": "COUPON_RANK_F1", "coupon_type": "fixed", "value": 80, "min_spend": 1000, "expire_days": 7}, {"item_id": "COUPON_RANK_D3", "coupon_type": "discount", "value": 70, "min_spend": 1000, "expire_days": 7}])
            resp = harness.recommend_http()
            assert resp['code'] == 0
            assert len(harness.rank_input_items) == 3
            assert harness.rank_input_items[:2] == ['COUPON_RANK_D1', 'COUPON_RANK_F1']
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_rank_010(self, setup_rough_ranking):
        """TC-RANK-010：truncate_count 超过候选数时不截断"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-010",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/business.md",
            "title": "truncate_count 超过候选数时不截断",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":10,"truncate_rule":"top_value"}
            # SETUP: 请求覆盖：请求只传入 1 张合法候选券

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_010", request_id="req-rank-010", params={"enable_coarse_rank": True, "truncate_count": 10, "truncate_rule": "top_value"}, items=[{"item_id": "COUPON_RANK_A", "coupon_type": "discount", "value": 100, "min_spend": 9000, "expire_days": 7}])
            resp = harness.recommend_http()
            assert resp['code'] == 0
            assert len(harness.rank_input_items) == 1
            assert harness.rank_input_items == ['COUPON_RANK_A']
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_rank_011(self, setup_rough_ranking):
        """TC-RANK-011：gRPC is_prior 字段映射为内部 isPrior"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-011",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/business.md",
            "title": "gRPC is_prior 字段映射为内部 isPrior",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：gRPC
            # SETUP: 请求覆盖：gRPC 请求中 COUPON_RANK_B.is_prior=true
            # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":1,"prior_count":1,"prior_rule":"top_value"}

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_011", request_id="req-rank-011", params={"enable_coarse_rank": True, "truncate_count": 1, "prior_count": 1, "prior_rule": "top_value"})
            resp = harness.recommend_grpc()
            assert resp['code'] == 0
            assert harness.rank_input_items == ['COUPON_RANK_B']
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_rank_012(self, setup_rough_ranking):
        """TC-RANK-012：完整粗排 pipeline 组合生效"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-012",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/business.md",
            "title": "完整粗排 pipeline 组合生效",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 请求覆盖：请求传入 8 个 item（含 3 个 isPrior=true）
            # SETUP: 策略参数：策略参数同时配置 prior_count=2、过滤 expire_days>=3、加权排序、类型打散 max_per_group=1、truncate_count=5

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_012", request_id="req-rank-012", params={"enable_coarse_rank": True, "truncate_count": 5, "prior_count": 2, "prior_rule": "top_value", "filters": [{"field": "expire_days", "op": "gte", "value": 3}], "sort_keys": [{"field": "value", "weight": 1.0}], "diversity": {"enabled": True, "group_field": "coupon_type", "max_per_group": 1}}, items=[{"item_id": "P1", "coupon_type": "discount", "value": 1000, "min_spend": 1000, "expire_days": 7, "isPrior": True}, {"item_id": "P2", "coupon_type": "fixed", "value": 900, "min_spend": 1000, "expire_days": 7, "isPrior": True}, {"item_id": "P3", "coupon_type": "free_shipping", "value": 100, "min_spend": 1000, "expire_days": 7, "isPrior": True}, {"item_id": "A", "coupon_type": "discount", "value": 800, "min_spend": 1000, "expire_days": 7}, {"item_id": "B", "coupon_type": "discount", "value": 700, "min_spend": 1000, "expire_days": 1}, {"item_id": "C", "coupon_type": "fixed", "value": 600, "min_spend": 1000, "expire_days": 7}, {"item_id": "D", "coupon_type": "fixed", "value": 500, "min_spend": 1000, "expire_days": 1}, {"item_id": "E", "coupon_type": "free_shipping", "value": 400, "min_spend": 1000, "expire_days": 7}])
            resp = harness.recommend_http()
            assert resp['code'] == 0
            assert harness.rank_input_items == ['P1', 'P2', 'A', 'C', 'E']
            assert harness.rank_input_items[:2] == ['P1', 'P2']
        finally:
            reset_case_context(__aitest_ctx_token)



__codegen_skipped__ = []
