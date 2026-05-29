# Auto-generated from test_workspace/suites/coupon_system/rough_ranking_smoke/boundary.md
# DO NOT EDIT — regenerate with: aitest codegen --suite-file test_workspace/suites/coupon_system/rough_ranking_smoke/suite.yaml
import pytest
from test_workspace.targets.coupon_system.helpers import http as http_helper
from test_workspace.targets.coupon_system.helpers import grpc_ops
from test_workspace.targets.coupon_system.fixtures.common import http_base_url, grpc_target, ab_base_url, redis_url, redis_tracker
from test_workspace.targets.coupon_system.fixtures.rough_ranking import setup_rough_ranking


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


class TestRoughRankingBoundary:
    """rough_ranking 边界测试用例"""

    # ── 一、空输入与截断边界 ──

    def test_tc_rank_013(self, setup_rough_ranking):
        """TC-RANK-013：候选券为空时参数校验拦截"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-013",
            "module": "rough_ranking",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/boundary.md",
            "title": "候选券为空时参数校验拦截",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 items=[]

        case = setup_rough_ranking
        case = setup_rough_ranking(case_id="TC-RANK-013")
        resp = case.recommend_http()
        assert resp['code'] == 1001
        assert resp['results'] == []
        assert case.rank_input_items == []

    def test_tc_rank_014(self, setup_rough_ranking):
        """TC-RANK-014：truncate_count 小于等于 0 时返回空推荐结果"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-014",
            "module": "rough_ranking",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/boundary.md",
            "title": "truncate_count 小于等于 0 时返回空推荐结果",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":0,"truncate_rule":"top_value"}
        # SETUP: 请求覆盖：HTTP 请求传入 3 张合法券

        case = setup_rough_ranking
        case = setup_rough_ranking(case_id="TC-RANK-014")
        resp = case.recommend_http()
        assert resp['code'] == 0
        assert resp['results'] == []
        assert resp['coupon'] is None
        assert case.rank_input_items == []

    def test_tc_rank_015(self, setup_rough_ranking):
        """TC-RANK-015：truncate_count 非数字时默认不截断"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-015",
            "module": "rough_ranking",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/boundary.md",
            "title": "truncate_count 非数字时默认不截断",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":"bad","truncate_rule":"top_value"}
        # SETUP: 请求覆盖：HTTP 请求传入 3 张合法券

        case = setup_rough_ranking
        case = setup_rough_ranking(case_id="TC-RANK-015")
        resp = case.recommend_http()
        assert resp['code'] == 0
        assert len(case.rank_input_items) == 3

    # ── 二、异常规则降级 ──

    @pytest.mark.manual
    def test_tc_rank_016(self, setup_rough_ranking):
        """TC-RANK-016：未知 truncate_rule 降级到 top_value"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-016",
            "module": "rough_ranking",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/boundary.md",
            "title": "未知 truncate_rule 降级到 top_value",
            "priority": "P2 / 异常",
            "markers": ["`[manual]`"],
        }
        # SETUP: 协议：HTTP
        # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":2,"truncate_rule":"unknown_rule"}
        # SETUP: 请求覆盖：HTTP 请求传入 A/B/C

        case = setup_rough_ranking
        case = setup_rough_ranking(case_id="TC-RANK-016")
        resp = case.recommend_http()
        assert resp['code'] == 0
        assert case.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
        # MANUAL CHECK: 应用日志包含 未知粗排规则

    def test_tc_rank_017(self, setup_rough_ranking):
        """TC-RANK-017：sort_keys 格式异常时跳过异常 key"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-017",
            "module": "rough_ranking",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/boundary.md",
            "title": "sort_keys 格式异常时跳过异常 key",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":2,"sort_keys":["bad",{"field":123,"weight":1},{"field":"value","weight":"bad"}]}

        case = setup_rough_ranking
        case = setup_rough_ranking(case_id="TC-RANK-017")
        resp = case.recommend_http()
        assert resp['code'] == 0
        assert len(case.rank_input_items) == 2

    @pytest.mark.manual
    def test_tc_rank_018(self, setup_rough_ranking):
        """TC-RANK-018：filters 操作符未知时该条件不通过"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-018",
            "module": "rough_ranking",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/boundary.md",
            "title": "filters 操作符未知时该条件不通过",
            "priority": "P2 / 异常",
            "markers": ["`[manual]`"],
        }
        # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":3,"filters":[{"field":"value","op":"bad_op","value":80}]}

        case = setup_rough_ranking
        case = setup_rough_ranking(case_id="TC-RANK-018")
        resp = case.recommend_http()
        assert resp['code'] == 0
        assert resp['results'] == []
        assert case.rank_input_items == []
        # MANUAL CHECK: 应用日志包含 未知过滤操作符

    def test_tc_rank_019(self, setup_rough_ranking):
        """TC-RANK-019：diversity 参数异常时跳过打散"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-019",
            "module": "rough_ranking",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/boundary.md",
            "title": "diversity 参数异常时跳过打散",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":2,"truncate_rule":"top_value","diversity":{"enabled":true,"group_field":123,"max_per_group":0}}

        case = setup_rough_ranking
        case = setup_rough_ranking(case_id="TC-RANK-019")
        resp = case.recommend_http()
        assert resp['code'] == 0
        assert case.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']

    @pytest.mark.manual
    def test_tc_rank_020(self, setup_rough_ranking):
        """TC-RANK-020：prior_count 大于 truncate_count 时截断到 truncate_count"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-020",
            "module": "rough_ranking",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/boundary.md",
            "title": "prior_count 大于 truncate_count 时截断到 truncate_count",
            "priority": "P2 / 异常",
            "markers": ["`[manual]`"],
        }
        # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":1,"prior_count":3,"prior_rule":"top_value"}
        # SETUP: 请求覆盖：B 为 isPrior=true

        case = setup_rough_ranking
        case = setup_rough_ranking(case_id="TC-RANK-020")
        resp = case.recommend_http()
        assert resp['code'] == 0
        assert case.rank_input_items == ['COUPON_RANK_B']
        # MANUAL CHECK: 应用日志包含 prior_count=3 大于 truncate_count=1

    def test_tc_rank_021(self, setup_rough_ranking):
        """TC-RANK-021：gRPC truncate_count 非数字时默认不截断"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-021",
            "module": "rough_ranking",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/boundary.md",
            "title": "gRPC truncate_count 非数字时默认不截断",
            "priority": "P2 / 异常",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":"bad","truncate_rule":"top_value"}
        # SETUP: 请求覆盖：gRPC 请求传入 3 张合法券

        case = setup_rough_ranking
        case = setup_rough_ranking(case_id="TC-RANK-021")
        resp = case.recommend_grpc()
        assert resp['code'] == 0
        assert len(case.rank_input_items) == 3

    @pytest.mark.manual
    def test_tc_rank_022(self, setup_rough_ranking):
        """TC-RANK-022：gRPC 未知 truncate_rule 降级到 top_value"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-022",
            "module": "rough_ranking",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/boundary.md",
            "title": "gRPC 未知 truncate_rule 降级到 top_value",
            "priority": "P2 / 异常",
            "markers": ["`[manual]`"],
        }
        # SETUP: 协议：gRPC
        # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":2,"truncate_rule":"unknown_rule"}
        # SETUP: 请求覆盖：gRPC 请求传入 A/B/C

        case = setup_rough_ranking
        case = setup_rough_ranking(case_id="TC-RANK-022")
        resp = case.recommend_grpc()
        assert resp['code'] == 0
        assert case.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
        # MANUAL CHECK: 应用日志包含 未知粗排规则

    @pytest.mark.manual
    def test_tc_rank_023(self, setup_rough_ranking):
        """TC-RANK-023：gRPC prior_count 大于 truncate_count 时截断到 truncate_count"""
        __tc_meta__ = {
            "tc_id": "TC-RANK-023",
            "module": "rough_ranking",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/rough_ranking_smoke/boundary.md",
            "title": "gRPC prior_count 大于 truncate_count 时截断到 truncate_count",
            "priority": "P2 / 异常",
            "markers": ["`[manual]`"],
        }
        # SETUP: 协议：gRPC
        # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":1,"prior_count":3,"prior_rule":"top_value"}
        # SETUP: 请求覆盖：gRPC 请求中 COUPON_RANK_B.is_prior=true

        case = setup_rough_ranking
        case = setup_rough_ranking(case_id="TC-RANK-023")
        resp = case.recommend_grpc()
        assert resp['code'] == 0
        assert case.rank_input_items == ['COUPON_RANK_B']
        # MANUAL CHECK: 应用日志包含 prior_count=3 大于 truncate_count=1


# TODO: setup_rough_ranking fixture 需要手写实现（→ tests/fixtures/rough_ranking.py）

__codegen_skipped__ = []
