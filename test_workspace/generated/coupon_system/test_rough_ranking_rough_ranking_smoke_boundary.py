# Auto-generated from test_workspace/suites/coupon_system/rough_ranking_smoke/boundary.md
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
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 请求覆盖：HTTP 请求 items=[]

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_013", request_id="req-rank-013", items=[])
            resp = harness.recommend_http()
            assert resp['code'] == 1001
            assert resp['results'] == []
            assert harness.rank_input_items == []
        finally:
            reset_case_context(__aitest_ctx_token)

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
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":0,"truncate_rule":"top_value"}
            # SETUP: 请求覆盖：HTTP 请求传入 3 张合法券

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_014", request_id="req-rank-014", params={"enable_coarse_rank": True, "truncate_count": 0, "truncate_rule": "top_value"})
            resp = harness.recommend_http()
            assert resp['code'] == 0
            assert resp['results'] == []
            assert resp['coupon'] is None
            assert harness.rank_input_items == []
        finally:
            reset_case_context(__aitest_ctx_token)

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
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":"bad","truncate_rule":"top_value"}
            # SETUP: 请求覆盖：HTTP 请求传入 3 张合法券

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_015", request_id="req-rank-015", params={"enable_coarse_rank": True, "truncate_count": "bad", "truncate_rule": "top_value"})
            resp = harness.recommend_http()
            assert resp['code'] == 0
            assert len(harness.rank_input_items) == 3
        finally:
            reset_case_context(__aitest_ctx_token)

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
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":2,"truncate_rule":"unknown_rule"}
            # SETUP: 请求覆盖：HTTP 请求传入 A/B/C

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_016", request_id="req-rank-016", params={"enable_coarse_rank": True, "truncate_count": 2, "truncate_rule": "unknown_rule"})
            resp = harness.recommend_http()
            assert resp['code'] == 0
            assert harness.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
            # MANUAL CHECK: 应用日志包含 未知粗排规则
        finally:
            reset_case_context(__aitest_ctx_token)

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
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":2,"sort_keys":["bad",{"field":123,"weight":1},{"field":"value","weight":"bad"}]}

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_017", request_id="req-rank-017", params={"enable_coarse_rank": True, "truncate_count": 2, "sort_keys": ["bad", {"field": 123, "weight": 1}, {"field": "value", "weight": "bad"}]})
            resp = harness.recommend_http()
            assert resp['code'] == 0
            assert len(harness.rank_input_items) == 2
        finally:
            reset_case_context(__aitest_ctx_token)

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
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":3,"filters":[{"field":"value","op":"bad_op","value":80}]}

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_018", request_id="req-rank-018", params={"enable_coarse_rank": True, "truncate_count": 3, "filters": [{"field": "value", "op": "bad_op", "value": 80}]})
            resp = harness.recommend_http()
            assert resp['code'] == 0
            assert resp['results'] == []
            assert harness.rank_input_items == []
            # MANUAL CHECK: 应用日志包含 未知过滤操作符
        finally:
            reset_case_context(__aitest_ctx_token)

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
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":2,"truncate_rule":"top_value","diversity":{"enabled":true,"group_field":123,"max_per_group":0}}

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_019", request_id="req-rank-019", params={"enable_coarse_rank": True, "truncate_count": 2, "truncate_rule": "top_value", "diversity": {"enabled": True, "group_field": 123, "max_per_group": 0}})
            resp = harness.recommend_http()
            assert resp['code'] == 0
            assert harness.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
        finally:
            reset_case_context(__aitest_ctx_token)

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
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":1,"prior_count":3,"prior_rule":"top_value"}
            # SETUP: 请求覆盖：B 为 isPrior=true

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_020", request_id="req-rank-020", params={"enable_coarse_rank": True, "truncate_count": 1, "prior_count": 3, "prior_rule": "top_value"})
            resp = harness.recommend_http()
            assert resp['code'] == 0
            assert harness.rank_input_items == ['COUPON_RANK_B']
            # MANUAL CHECK: 应用日志包含 prior_count=3 大于 truncate_count=1
        finally:
            reset_case_context(__aitest_ctx_token)

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
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：gRPC
            # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":"bad","truncate_rule":"top_value"}
            # SETUP: 请求覆盖：gRPC 请求传入 3 张合法券

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_021", request_id="req-rank-021", params={"enable_coarse_rank": True, "truncate_count": "bad", "truncate_rule": "top_value"})
            resp = harness.recommend_grpc()
            assert resp['code'] == 0
            assert len(harness.rank_input_items) == 3
        finally:
            reset_case_context(__aitest_ctx_token)

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
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：gRPC
            # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":2,"truncate_rule":"unknown_rule"}
            # SETUP: 请求覆盖：gRPC 请求传入 A/B/C

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_022", request_id="req-rank-022", params={"enable_coarse_rank": True, "truncate_count": 2, "truncate_rule": "unknown_rule"})
            resp = harness.recommend_grpc()
            assert resp['code'] == 0
            assert harness.rank_input_items == ['COUPON_RANK_A', 'COUPON_RANK_B']
            # MANUAL CHECK: 应用日志包含 未知粗排规则
        finally:
            reset_case_context(__aitest_ctx_token)

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
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：gRPC
            # SETUP: 策略参数：{"enable_coarse_rank":true,"truncate_count":1,"prior_count":3,"prior_rule":"top_value"}
            # SETUP: 请求覆盖：gRPC 请求中 COUPON_RANK_B.is_prior=true

            harness = setup_rough_ranking
            harness.prepare(user_id="u_rank_023", request_id="req-rank-023", params={"enable_coarse_rank": True, "truncate_count": 1, "prior_count": 3, "prior_rule": "top_value"})
            resp = harness.recommend_grpc()
            assert resp['code'] == 0
            assert harness.rank_input_items == ['COUPON_RANK_B']
            # MANUAL CHECK: 应用日志包含 prior_count=3 大于 truncate_count=1
        finally:
            reset_case_context(__aitest_ctx_token)



__codegen_skipped__ = []
