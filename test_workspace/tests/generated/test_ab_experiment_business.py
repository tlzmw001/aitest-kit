# Auto-generated from test_workspace/cases/ab_experiment/business.md
# DO NOT EDIT — regenerate with: /test-codegen ab_experiment
import pytest
from test_workspace.tests.helpers import http as http_helper
from test_workspace.tests.helpers import grpc_ops


class TestAbExperimentBusiness:
    """ab_experiment 业务测试用例"""

    # ── 一、SDK 分流 ──

    def test_tc_ab_001(self, http_base_url, setup_ab_experiment):
        """TC-AB-001：HTTP 通过 hash 命中场景关联实验"""
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_ab_hash_http"、scene_name="game"、device="mobile"、external=0、reqId="req-ab-001"
        # SETUP: 前置操作：不设置该用户白名单
        setup_ab_experiment(case_id="TC-AB-001")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_ab_001", "req_ab_001"))
        assert isinstance(resp, dict)
        assert isinstance(resp, dict)
        assert resp["code"] == 0
        assert set(resp["experiment_info"].keys()) <= {"coarse_rank_exp_game", "calibration_exp_game"}
        assert "coarse_rank_exp_ad" not in resp["experiment_info"] and "calibration_exp_ad" not in resp["experiment_info"]

    def test_tc_ab_002(self, grpc_target, setup_ab_experiment):
        """TC-AB-002：gRPC 通过 hash 命中场景关联实验"""
        # SETUP: 协议：gRPC
        # SETUP: 请求覆盖：gRPC 请求 user_id="u_ab_hash_grpc"、scene_name="ad"、device="pc"、external=0、req_id="req-ab-002"
        # SETUP: 前置操作：不设置该用户白名单
        setup_ab_experiment(case_id="TC-AB-002")

        resp = grpc_ops.recommend(grpc_target, _req("u_ab_002", "req_ab_002"))
        assert isinstance(resp, dict)
        assert isinstance(resp, dict)
        assert resp["code"] == 0
        assert set(resp["experiment_info"].keys()) <= {"coarse_rank_exp_ad", "calibration_exp_ad"}
        assert "coarse_rank_exp_game" not in resp["experiment_info"] and "calibration_exp_game" not in resp["experiment_info"]

    def test_tc_ab_003(self, http_base_url, setup_ab_experiment):
        """TC-AB-003：白名单优先级高于 hash 分流"""
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：先执行 PUT /api/v1/ab/whitelist/u_ab_white，body 为 {"strategy_map":{"coarse_rank_exp_game":"cr_off","calibration_exp_game":"cal_off"}}
        # SETUP: 请求覆盖_2：HTTP 请求 user_id="u_ab_white"、scene_name="game"、device="mobile"、external=0、reqId="req-ab-003"
        setup_ab_experiment(case_id="TC-AB-003")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_ab_003", "req_ab_003"))
        assert isinstance(resp, dict)
        assert isinstance(resp, dict)
        assert resp["code"] == 0
        assert resp["experiment_info"].get("coarse_rank_exp_game") == "cr_off"
        assert resp["experiment_info"].get("calibration_exp_game") == "cal_off"

    # ── 二、场景实验映射 ──

    def test_tc_ab_004(self, http_base_url, setup_ab_experiment):
        """TC-AB-004：只评估当前 scene_id 映射的实验"""
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_ab_scene_game"、scene_name="game"、device="mobile"、external=0
        # SETUP: 请求覆盖_2：AB 服务中同时存在 game/ad 两组实验
        setup_ab_experiment(case_id="TC-AB-004")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_ab_004", "req_ab_004"))
        assert isinstance(resp, dict)
        assert isinstance(resp, dict)
        assert resp["code"] == 0
        assert set(resp["experiment_info"].keys()) <= {"coarse_rank_exp_game", "calibration_exp_game"}
        assert not any(k.endswith("_ad") for k in resp["experiment_info"])

    def test_tc_ab_005(self, http_base_url, setup_ab_experiment):
        """TC-AB-005：场景无实验映射时返回空实验信息"""
        # SETUP: 协议：HTTP
        # SETUP: 环境覆盖：测试环境将场景实验映射中目标 scene_id 配置为空列表后启动主服务
        # SETUP: 请求覆盖：HTTP 请求命中该 scene_id
        setup_ab_experiment(case_id="TC-AB-005")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_ab_005", "req_ab_005"))
        assert isinstance(resp, dict)
        assert isinstance(resp, dict)
        assert resp["code"] == 0
        assert resp["code"] == 0
        assert resp["experiment_info"] == {}

    # ── 三、外部打分隔离 ──

    def test_tc_ab_006(self, http_base_url, setup_ab_experiment):
        """TC-AB-006：HTTP external=1 时不获取任何实验"""
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_ab_external_http"、scene_name="game"、device="mobile"、external=1、reqId="req-ab-006"
        # SETUP: 请求覆盖_2：AB 服务可用且存在可命中实验
        setup_ab_experiment(case_id="TC-AB-006")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_ab_006", "req_ab_006"))
        assert isinstance(resp, dict)
        assert isinstance(resp, dict)
        assert resp["code"] == 0
        assert resp["experiment_info"] == {}

    def test_tc_ab_007(self, grpc_target, setup_ab_experiment):
        """TC-AB-007：gRPC external=1 时不获取任何实验"""
        # SETUP: 协议：gRPC
        # SETUP: 请求覆盖：gRPC 请求 user_id="u_ab_external_grpc"、scene_name="game"、device="mobile"、external=1、req_id="req-ab-007"
        # SETUP: 请求覆盖_2：AB 服务可用且存在可命中实验
        setup_ab_experiment(case_id="TC-AB-007")

        resp = grpc_ops.recommend(grpc_target, _req("u_ab_007", "req_ab_007"))
        assert isinstance(resp, dict)
        assert isinstance(resp, dict)
        assert resp["code"] == 0
        assert resp["experiment_info"] == {}

    # ── 四、异常场景 ──

    @pytest.mark.manual
    def test_tc_ab_009(self, http_base_url, setup_ab_experiment):
        """TC-AB-009：实验名不存在时静默跳过"""
        # SETUP: 协议：HTTP
        # SETUP: 前置操作：测试环境将 scene_id=1001 的实验映射设为 ["coarse_rank_exp_game","not_exists_exp"]
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_ab_unknown_exp"、scene_name="game"、device="mobile"、external=0
        setup_ab_experiment(case_id="TC-AB-009")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_ab_009", "req_ab_009"))
        # MANUAL CHECK: response.body.code == 0
        # MANUAL CHECK: exp 不包含 not_exists_exp
        # MANUAL CHECK: 应用日志包含 ab_sdk unknown experiment: not_exists_exp


# SKIPPED: TC-AB-008 — `[!可行性存疑: 需要测试环境允许控制 AB 服务可用性或启动参数]`
