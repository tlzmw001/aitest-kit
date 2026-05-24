# Auto-generated from test_workspace/cases/rough_ranking/business.md
# DO NOT EDIT — regenerate with: /test-codegen rough_ranking
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
    "items": [{"item_id": "COUPON_RANK_A", "coupon_type": "discount", "value": 100, "min_spend": 9000, "expire_days": 7}, {"item_id": "COUPON_RANK_B", "coupon_type": "fixed", "value": 80, "min_spend": 1000, "expire_days": 7, "isPrior": True}, {"item_id": "COUPON_RANK_C", "coupon_type": "free_shipping", "value": 50, "min_spend": 500, "expire_days": 7}],
}


def _req(**overrides) -> dict:
    body = {**BASE_REQUEST}
    body.update(overrides)
    return body


class TestRoughRankingBusiness:
    """rough_ranking 业务测试用例"""

    # ── 一、实验控制 ──

    def test_tc_rank_001(self, setup_rough_ranking):
        """TC-RANK-001：HTTP 实验关闭时跳过粗排"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-001",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/cases/rough_ranking/business.md",
            "title": "HTTP 实验关闭时跳过粗排",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 前置操作：白名单命中粗排关闭策略 enable_coarse_rank=false
        # SETUP: 请求覆盖：HTTP 请求按 A,B,C 顺序传入 3 张券

        case = setup_rough_ranking(case_id="TC-RANK-001")
        resp = case.recommend_http()
        assert resp['code'] == 0
        assert case.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B', 'COUPON_RANK_C']

    def test_tc_rank_002(self, setup_rough_ranking):
        """TC-RANK-002：gRPC 实验开启且不配置增强能力时保持向后兼容"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-002",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/cases/rough_ranking/business.md",
            "title": "gRPC 实验开启且不配置增强能力时保持向后兼容",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 策略参数：白名单命中{"enable_coarse_rank":true,"truncate_count":3}，不配置 prior_count、filters、sort_keys、diversity
        # SETUP: 请求覆盖：gRPC 请求按 A,B,C 顺序传入 3 张券

        case = setup_rough_ranking(case_id="TC-RANK-002")
        resp = case.recommend_grpc()
        assert resp['code'] == 0
        assert case.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B', 'COUPON_RANK_C']

    # ── 二、基础截断 ──

    def test_tc_rank_003(self, setup_rough_ranking):
        """TC-RANK-003：top_value 按面额降序截断"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-003",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/cases/rough_ranking/business.md",
            "title": "top_value 按面额降序截断",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":2,"truncate_rule":"top_value"}
        # SETUP: 请求覆盖：HTTP 请求传入 A/B/C

        case = setup_rough_ranking(case_id="TC-RANK-003")
        resp = case.recommend_http()
        assert resp['code'] == 0
        assert case.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']

    def test_tc_rank_004(self, setup_rough_ranking):
        """TC-RANK-004：top_min_spend 按门槛降序截断"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-004",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/cases/rough_ranking/business.md",
            "title": "top_min_spend 按门槛降序截断",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":2,"truncate_rule":"top_min_spend"}
        # SETUP: 请求覆盖：HTTP 请求传入 A/B/C

        case = setup_rough_ranking(case_id="TC-RANK-004")
        resp = case.recommend_http()
        assert resp['code'] == 0
        assert case.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']

    def test_tc_rank_005(self, setup_rough_ranking):
        """TC-RANK-005：random 截断只保证数量和来源"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-005",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/cases/rough_ranking/business.md",
            "title": "random 截断只保证数量和来源",
            "priority": "P2",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":2,"truncate_rule":"random"}
        # SETUP: 请求覆盖：HTTP 请求传入 A/B/C

        case = setup_rough_ranking(case_id="TC-RANK-005")
        resp = case.recommend_http()
        assert resp['code'] == 0
        assert len(case.rank_input_items) == 2
        assert set(case.rank_input_items) <= {'COUPON_RANK_A', 'COUPON_RANK_B', 'COUPON_RANK_C'}

    # ── 三、增强能力 ──

    def test_tc_rank_006(self, setup_rough_ranking):
        """TC-RANK-006：优先券保送后普通券补位"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-006",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/cases/rough_ranking/business.md",
            "title": "优先券保送后普通券补位",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":2,"prior_count":1,"prior_rule":"top_value","truncate_rule":"top_value"}
        # SETUP: 请求覆盖：B 为 isPrior=true

        case = setup_rough_ranking(case_id="TC-RANK-006")
        resp = case.recommend_http()
        assert resp['code'] == 0
        assert case.rank_input_items[0] == 'COUPON_RANK_B'
        assert len(case.rank_input_items) == 2

    def test_tc_rank_007(self, setup_rough_ranking):
        """TC-RANK-007：多条件过滤取交集"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-007",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/cases/rough_ranking/business.md",
            "title": "多条件过滤取交集",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":3,"filters":[{"field":"value","op":"gte","value":80},{"field":"coupon_type","op":"in","value":["discount","fixed"]}]}

        case = setup_rough_ranking(case_id="TC-RANK-007")
        resp = case.recommend_http()
        assert resp['code'] == 0
        assert case.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']

    def test_tc_rank_008(self, setup_rough_ranking):
        """TC-RANK-008：多维排序按加权分排序"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-008",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/cases/rough_ranking/business.md",
            "title": "多维排序按加权分排序",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":3,"sort_keys":[{"field":"value","weight":1.0},{"field":"min_spend","weight":-1.0}]}

        case = setup_rough_ranking(case_id="TC-RANK-008")
        resp = case.recommend_http()
        assert resp['code'] == 0
        assert case.rank_input_items[0] == 'COUPON_RANK_B'

    def test_tc_rank_009(self, setup_rough_ranking):
        """TC-RANK-009：类型打散限制同类型数量并回填"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-009",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/cases/rough_ranking/business.md",
            "title": "类型打散限制同类型数量并回填",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 请求覆盖：请求传入 4 张券，其中 3 张 coupon_type="discount"、1 张 coupon_type="fixed"
        # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":3,"truncate_rule":"top_value","diversity":{"enabled":true,"group_field":"coupon_type","max_per_group":1}}

        case = setup_rough_ranking(case_id="TC-RANK-009")
        resp = case.recommend_http()
        assert resp['code'] == 0
        assert len(case.rank_input_items) == 3
        assert case.rank_input_items[:2] == ['COUPON_RANK_D1', 'COUPON_RANK_F1']

    def test_tc_rank_010(self, setup_rough_ranking):
        """TC-RANK-010：truncate_count 超过候选数时不截断"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-010",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/cases/rough_ranking/business.md",
            "title": "truncate_count 超过候选数时不截断",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":10,"truncate_rule":"top_value"}
        # SETUP: 请求覆盖：请求只传入 1 张合法候选券

        case = setup_rough_ranking(case_id="TC-RANK-010")
        resp = case.recommend_http()
        assert resp['code'] == 0
        assert len(case.rank_input_items) == 1
        assert case.rank_input_items == ['COUPON_RANK_A']

    def test_tc_rank_011(self, setup_rough_ranking):
        """TC-RANK-011：gRPC is_prior 字段映射为内部 isPrior"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-011",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/cases/rough_ranking/business.md",
            "title": "gRPC is_prior 字段映射为内部 isPrior",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 请求覆盖：gRPC 请求中 COUPON_RANK_B.is_prior=true
        # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":1,"prior_count":1,"prior_rule":"top_value"}

        case = setup_rough_ranking(case_id="TC-RANK-011")
        resp = case.recommend_grpc()
        assert resp['code'] == 0
        assert case.rank_input_items == ['COUPON_RANK_B']

    def test_tc_rank_012(self, setup_rough_ranking):
        """TC-RANK-012：完整粗排 pipeline 组合生效"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-012",
            "module": "rough_ranking",
            "category": "business",
            "source": "test_workspace/cases/rough_ranking/business.md",
            "title": "完整粗排 pipeline 组合生效",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 请求覆盖：请求传入 8 个 item（含 3 个 isPrior=true）
        # SETUP: 策略参数：策略参数同时配置 prior_count=2、过滤 expire_days>=3、加权排序、类型打散 max_per_group=1、truncate_count=5

        case = setup_rough_ranking(case_id="TC-RANK-012")
        resp = case.recommend_http()
        assert resp['code'] == 0
        assert case.rank_input_items == ['P1', 'P2', 'A', 'C', 'E']
        assert case.rank_input_items[:2] == ['P1', 'P2']



__codegen_skipped__ = []
