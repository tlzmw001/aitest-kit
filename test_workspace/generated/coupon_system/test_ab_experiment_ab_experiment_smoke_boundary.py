# Auto-generated from test_workspace/suites/coupon_system/ab_experiment_smoke/boundary.md
# DO NOT EDIT — regenerate with: aitest codegen --suite-file test_workspace/suites/coupon_system/ab_experiment_smoke/suite.yaml
import pytest
from test_workspace.targets.coupon_system.helpers import http as http_helper
from aitest_kit.helpers.request_binding import build_request
from aitest_kit.runtime_context import reset_case_context, set_case_context
pytest_plugins = ["test_workspace.targets.coupon_system.modules.ab_experiment.fixture"]


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
    "items": [{"item_id": "COUPON_AB_BOUNDARY_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}],
}


def _req(*, auto_fields=None, overrides=None, patches=None) -> dict:
    return build_request(
        BASE_REQUEST,
        auto_fields=auto_fields or {},
        overrides=overrides or {},
        patches=patches or [],
    )


class TestAbExperimentBoundary:
    """ab_experiment 边界测试用例"""

    # ── 一、hash 区间边界 ──

    def test_tc_ab_011(self, setup_ab_experiment):
        """TC-AB-011：hash 不命中区间右开边界"""
        __tc_meta__ = {
            "tc_id": "TC-AB-011",
            "module": "ab_experiment",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_experiment_smoke/boundary.md",
            "title": "hash 不命中区间右开边界",
            "priority": "P2",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 前置操作：通过 AB 服务创建实验 ab_boundary_right，策略 right_miss 的 hash_range=[0,H]
            # SETUP: 前置操作_2：选择 md5(user_id)%100 == H 的 user_id
            # SETUP: 前置操作_3：将 scene_id=1001 映射到该实验

            harness = setup_ab_experiment
            harness.prepare_stock(coupon_id="COUPON_AB_BOUNDARY_001", stock=100)
            resp = harness.recommend_http(request_overrides={"user_id": "u_ab_boundary_right", "reqId": "req-ab-011", "items": [{"item_id": "COUPON_AB_BOUNDARY_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}]})
            assert resp["code"] == 0
            assert "ab_boundary_right" not in resp["experiment_info"]
        finally:
            reset_case_context(__aitest_ctx_token)

    # ── 二、白名单容错 ──

    @pytest.mark.manual
    def test_tc_ab_012(self):
        """TC-AB-012：白名单 strategy_id 无效时降级 hash 分流"""
        __tc_meta__ = {
            "tc_id": "TC-AB-012",
            "module": "ab_experiment",
            "category": "boundary",
            "source": "test_workspace/suites/coupon_system/ab_experiment_smoke/boundary.md",
            "title": "白名单 strategy_id 无效时降级 hash 分流",
            "priority": "P2 / 异常",
            "markers": ["`[manual]`"],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 协议：HTTP
            # SETUP: 接口调用：PUT /api/v1/ab/whitelist/u_ab_invalid_white，body 为 {"strategy_map":{"coarse_rank_exp_game":"not_exists_strategy"}}
            # SETUP: 请求覆盖：HTTP 请求 user_id="u_ab_invalid_white"、reqId="req-ab-012"
            # MANUAL CHECK: exp["coarse_rank_exp_game"] != "not_exists_strategy"
            # MANUAL CHECK: AB 服务日志包含 ab_sdk whitelist invalid
            pytest.skip("manual check required")
        finally:
            reset_case_context(__aitest_ctx_token)


# SKIPPED: TC-AB-010 — `[!可行性存疑: 已确认为待测系统缺陷，主服务不支持运行时热更新 scene_experiments.json，详见 results/ab_experiment_scene_experiments_hot_reload_bug.md]`
# SKIPPED: TC-AB-013 — `[!可行性存疑: 需要测试环境支持本地 SDK 模式启动主服务]`
# SKIPPED: TC-AB-014 — `[!可行性存疑: 需要测试环境提供慢响应 AB 服务]`
# SKIPPED: TC-AB-015 — `[!可行性存疑: 需要测试环境允许控制 AB 服务启动顺序并在同一用例内重试请求]`

__codegen_skipped__ = [{"tc_id": "TC-AB-010", "module": "ab_experiment", "category": "boundary", "source": "test_workspace/suites/coupon_system/ab_experiment_smoke/boundary.md", "title": "hash 命中区间左闭边界", "priority": "P2", "markers": ["`[!可行性存疑: 已确认为待测系统缺陷，主服务不支持运行时热更新 scene_experiments.json，详见 results/ab_experiment_scene_experiments_hot_reload_bug.md]`"], "reason": "`[!可行性存疑: 已确认为待测系统缺陷，主服务不支持运行时热更新 scene_experiments.json，详见 results/ab_experiment_scene_experiments_hot_reload_bug.md]`"}, {"tc_id": "TC-AB-013", "module": "ab_experiment", "category": "boundary", "source": "test_workspace/suites/coupon_system/ab_experiment_smoke/boundary.md", "title": "本地 SDK 白名单环境变量格式错误时忽略白名单", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 需要测试环境支持本地 SDK 模式启动主服务]`"], "reason": "`[!可行性存疑: 需要测试环境支持本地 SDK 模式启动主服务]`"}, {"tc_id": "TC-AB-014", "module": "ab_experiment", "category": "boundary", "source": "test_workspace/suites/coupon_system/ab_experiment_smoke/boundary.md", "title": "远程 SDK 超时直接导致请求失败", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 需要测试环境提供慢响应 AB 服务]`"], "reason": "`[!可行性存疑: 需要测试环境提供慢响应 AB 服务]`"}, {"tc_id": "TC-AB-015", "module": "ab_experiment", "category": "boundary", "source": "test_workspace/suites/coupon_system/ab_experiment_smoke/boundary.md", "title": "主服务早于 AB 服务启动时首个实验请求失败", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 需要测试环境允许控制 AB 服务启动顺序并在同一用例内重试请求]`"], "reason": "`[!可行性存疑: 需要测试环境允许控制 AB 服务启动顺序并在同一用例内重试请求]`"}]
