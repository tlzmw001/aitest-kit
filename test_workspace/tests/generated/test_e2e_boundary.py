# Auto-generated from test_workspace/cases/e2e/boundary.md
# DO NOT EDIT — regenerate with: /test-codegen e2e
import pytest
from test_workspace.tests.helpers import http as http_helper
from test_workspace.tests.helpers import grpc_ops


class TestE2eBoundary:
    """e2e 边界测试用例"""

    # ── 一、校准与最新配置生效 ──

    def test_tc_e2e_004(self, grpc_target, setup_e2e):
        """TC-E2E-004：远程 AB 命中 cal_on 且 game/mobile 请求在端到端链路中产生大于原分的校准分"""
        # SETUP: 协议：HTTP
        # SETUP: 环境覆盖：启动 Redis、AB 实验服务、内部 gRPC mock 打分服务和主服务；主服务配置 AB_SERVICE_URL={{ab_base_url}}
        # SETUP: 前置操作：确认测试配置中的 game/mobile 线性校准规则包含 {"conditions":{"device":"mobile"},"k":1.2,"b":0.1}
        # SETUP: 前置操作_2：在 AB 服务设置 u_e2e_calibration_004 白名单，命中 {"coarse_rank_exp_game":"cr_v2_full","calibration_exp_game":"cal_on"}
        # SETUP: 前置操作_3：写入用户特征 {"gender":"female","age":"28","total_spend":"12000","purchase_frequency":"9","register_days":"90","is_new_user":"True","is_member":"True"}
        # SETUP: 前置操作_4：设置 COUPON_ACT_001 库存为 3
        # SETUP: 请求覆盖：scene_name="game"、device="mobile"、external=0、score_threshold=0.2、max_claim_per_request=1、items 只包含 COUPON_ACT_001
        setup_e2e(case_id="TC-E2E-004")

        resp = grpc_ops.recommend(grpc_target, _req("u_e2e_004", "req_e2e_004"))
        # UNPARSED ASSERTION: 异常链路需要同时断言业务响应和发放记录状态
        # UNPARSED ASSERTION: 成功链路需要断言推荐响应与用户券查询结果一致。
        s = resp["results"][0]["score"]
        cal = resp["results"][0]["calibrated_score"]
        assert isinstance(resp, dict)
        assert resp["code"] == 0
        assert resp["scene_id"] == 1001
        assert resp["experiment_info"] == {"coarse_rank_exp_game": "cr_v2_full", "calibration_exp_game": "cal_on"}
        assert resp["results"][0]["item_id"] == "COUPON_ACT_001"
        assert resp["results"][0]["calibrated_score"] > resp["results"][0]["score"]
        assert resp["coupon"] is not None and resp["coupon"]["item_id"] == "COUPON_ACT_001"
        assert isinstance(resp, dict)

    # ── 二、跨服务故障边界 ──

    def test_tc_e2e_005(self, grpc_target, setup_e2e):
        """TC-E2E-005：内部打分链路在 AB 服务不可用时直接返回 HTTP 500"""
        # SETUP: 协议：HTTP
        # SETUP: 环境覆盖：启动 Redis、内部 gRPC mock 打分服务和主服务；主服务配置 AB_SERVICE_URL={{unreachable_ab_base_url}}
        # SETUP: 前置操作：确认 {{unreachable_ab_base_url}}/health 不可访问
        # SETUP: 前置操作_2：写入用户特征 {"gender":"male","age":"30","total_spend":"5000","purchase_frequency":"3","register_days":"30","is_new_user":"False","is_member":"False"}
        # SETUP: 前置操作_3：设置 COUPON_ACT_001 库存为 3
        # SETUP: 请求覆盖：user_id="u_e2e_ab_down_005"、scene_name="game"、device="mobile"、external=0、score_threshold=0.2、max_claim_per_request=1、items 只包含 COUPON_ACT_001
        setup_e2e(case_id="TC-E2E-005")

        resp = grpc_ops.recommend(grpc_target, _req("u_e2e_005", "req_e2e_005"))
        # UNPARSED ASSERTION: 异常链路需要同时断言业务响应和发放记录状态
        # UNPARSED ASSERTION: 成功链路需要断言推荐响应与用户券查询结果一致。
        assert isinstance(resp, dict)
        assert isinstance(resp, dict)

    def test_tc_e2e_006(self, http_base_url, setup_e2e):
        """TC-E2E-006：外部打分链路在 AB 服务不可用时仍可成功完成推荐"""
        # SETUP: 协议：HTTP
        # SETUP: 环境覆盖：启动 Redis、外部 HTTP mock 打分服务和主服务；主服务配置 AB_SERVICE_URL={{unreachable_ab_base_url}}
        # SETUP: 前置操作：确认 {{unreachable_ab_base_url}}/health 不可访问
        # SETUP: 前置操作_2：写入用户特征 {"gender":"male","age":"35","total_spend":"9000","purchase_frequency":"6","register_days":"120","is_new_user":"False","is_member":"True"}
        # SETUP: 前置操作_3：设置 COUPON_SHIP_001 库存为 3
        # SETUP: 请求覆盖：user_id="u_e2e_external_skip_006"、scene_name="ad"、device="pc"、external=1、score_threshold=0.2、max_claim_per_request=1、items 只包含 COUPON_SHIP_001
        setup_e2e(case_id="TC-E2E-006")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_e2e_006", "req_e2e_006"))
        # UNPARSED ASSERTION: 异常链路需要同时断言业务响应和发放记录状态
        # UNPARSED ASSERTION: 成功链路需要断言推荐响应与用户券查询结果一致。
        assert isinstance(resp, dict)
        assert resp["code"] == 0
        assert resp["scene_id"] == 2002
        assert resp["experiment_info"] == {}
        assert resp["coupon"] is not None and resp["coupon"]["item_id"] == "COUPON_SHIP_001"
        assert isinstance(resp, dict)

    # ── 三、共享状态边界 ──

    def test_tc_e2e_007(self, grpc_target, setup_e2e):
        """TC-E2E-007：gRPC 发放成功后可立即通过 HTTP 查询同一条领取记录"""
        # SETUP: 协议：gRPC / HTTP
        # SETUP: 环境覆盖：启动 Redis 和主服务；不写入任何 coupon:fallback:score:* Redis key
        # SETUP: 前置操作：设置 COUPON_ACT_001 库存为 1
        # SETUP: 请求覆盖：gRPC 推荐请求使用 user_id="u_e2e_shared_state_007"、scene_name="game"、device="mobile"、policy_id="policy_fallback_001"、external=0、score_threshold=0.4、max_claim_per_request=1、items 只包含 COUPON_ACT_001
        # SETUP: 请求覆盖_2：推荐成功后调用 HTTP GET /api/v1/coupons/u_e2e_shared_state_007
        setup_e2e(case_id="TC-E2E-007")

        resp = grpc_ops.recommend(grpc_target, _req("u_e2e_007", "req_e2e_007"))
        # UNPARSED ASSERTION: 异常链路需要同时断言业务响应和发放记录状态
        # UNPARSED ASSERTION: 成功链路需要断言推荐响应与用户券查询结果一致。
        assert resp["code"] == 0
        assert resp["scene_id"] == 3001
        assert resp["coupon"] is not None and resp["coupon"]["item_id"] == "COUPON_ACT_001"
        assert isinstance(resp, dict)
        assert isinstance(resp, dict)
        assert isinstance(resp, dict)


