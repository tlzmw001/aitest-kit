# Auto-generated from test_workspace/cases/ab_experiment/boundary.md
# DO NOT EDIT — regenerate with: /test-codegen ab_experiment
import pytest
from test_workspace.tests.helpers import http as http_helper


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


def _req(user_id: str, req_id: str, **overrides) -> dict:
    body = {**BASE_REQUEST, "user_id": user_id, "reqId": req_id}
    body.update(overrides)
    return body


class TestAbExperimentBoundary:
    """ab_experiment 边界测试用例"""

    # ── 一、hash 区间边界 ──

    def test_tc_ab_011(self, http_base_url, setup_ab_experiment):
        """TC-AB-011：hash 不命中区间右开边界"""
        __tc_meta__ = {
            "tc_id": "TC-AB-011",
            "module": "ab_experiment",
            "category": "boundary",
            "source": "test_workspace/cases/ab_experiment/boundary.md",
            "title": "hash 不命中区间右开边界",
            "priority": "P2",
            "markers": [],
        }
        # SETUP: 前置操作：通过 AB 服务创建实验 ab_boundary_right，策略 right_miss 的 hash_range=[0,H]
        # SETUP: 前置操作_2：选择 md5(user_id)%100 == H 的 user_id
        # SETUP: 前置操作_3：将 scene_id=1001 映射到该实验
        setup_ab_experiment(case_id="TC-AB-011")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_ab_011", "req_ab_011"))
        assert resp["code"] == 0
        assert "ab_boundary_right" not in resp["experiment_info"]

    # ── 二、白名单容错 ──

    @pytest.mark.manual
    def test_tc_ab_012(self, http_base_url, setup_ab_experiment):
        """TC-AB-012：白名单 strategy_id 无效时降级 hash 分流"""
        __tc_meta__ = {
            "tc_id": "TC-AB-012",
            "module": "ab_experiment",
            "category": "boundary",
            "source": "test_workspace/cases/ab_experiment/boundary.md",
            "title": "白名单 strategy_id 无效时降级 hash 分流",
            "priority": "P2 / 异常",
            "markers": ["`[manual]`"],
        }
        # SETUP: 协议：HTTP
        # SETUP: 接口调用：PUT /api/v1/ab/whitelist/u_ab_invalid_white，body 为 {"strategy_map":{"coarse_rank_exp_game":"not_exists_strategy"}}
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_ab_invalid_white"、reqId="req-ab-012"
        setup_ab_experiment(case_id="TC-AB-012")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_ab_012", "req_ab_012"))
        # MANUAL CHECK: exp["coarse_rank_exp_game"] != "not_exists_strategy"
        # MANUAL CHECK: AB 服务日志包含 ab_sdk whitelist invalid


# SKIPPED: TC-AB-010 — `[!可行性存疑: 已确认为待测系统缺陷，主服务不支持运行时热更新 scene_experiments.json，详见 results/ab_experiment_scene_experiments_hot_reload_bug.md]`
# SKIPPED: TC-AB-013 — `[!可行性存疑: 需要测试环境支持本地 SDK 模式启动主服务]`
# SKIPPED: TC-AB-014 — `[!可行性存疑: 需要测试环境提供慢响应 AB 服务]`
# SKIPPED: TC-AB-015 — `[!可行性存疑: 需要测试环境允许控制 AB 服务启动顺序并在同一用例内重试请求]`

__codegen_skipped__ = [{"tc_id": "TC-AB-010", "module": "ab_experiment", "category": "boundary", "source": "test_workspace/cases/ab_experiment/boundary.md", "title": "hash 命中区间左闭边界", "priority": "P2", "markers": ["`[!可行性存疑: 已确认为待测系统缺陷，主服务不支持运行时热更新 scene_experiments.json，详见 results/ab_experiment_scene_experiments_hot_reload_bug.md]`"], "reason": "`[!可行性存疑: 已确认为待测系统缺陷，主服务不支持运行时热更新 scene_experiments.json，详见 results/ab_experiment_scene_experiments_hot_reload_bug.md]`"}, {"tc_id": "TC-AB-013", "module": "ab_experiment", "category": "boundary", "source": "test_workspace/cases/ab_experiment/boundary.md", "title": "本地 SDK 白名单环境变量格式错误时忽略白名单", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 需要测试环境支持本地 SDK 模式启动主服务]`"], "reason": "`[!可行性存疑: 需要测试环境支持本地 SDK 模式启动主服务]`"}, {"tc_id": "TC-AB-014", "module": "ab_experiment", "category": "boundary", "source": "test_workspace/cases/ab_experiment/boundary.md", "title": "远程 SDK 超时直接导致请求失败", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 需要测试环境提供慢响应 AB 服务]`"], "reason": "`[!可行性存疑: 需要测试环境提供慢响应 AB 服务]`"}, {"tc_id": "TC-AB-015", "module": "ab_experiment", "category": "boundary", "source": "test_workspace/cases/ab_experiment/boundary.md", "title": "主服务早于 AB 服务启动时首个实验请求失败", "priority": "P2 / 异常", "markers": ["`[!可行性存疑: 需要测试环境允许控制 AB 服务启动顺序并在同一用例内重试请求]`"], "reason": "`[!可行性存疑: 需要测试环境允许控制 AB 服务启动顺序并在同一用例内重试请求]`"}]
