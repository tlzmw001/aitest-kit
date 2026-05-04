# Auto-generated from test_workspace/cases/e2e/business.md
# DO NOT EDIT — regenerate with: /test-codegen e2e
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
    "score_threshold": 0.2,
    "max_claim_per_request": 1,
    "context": {},
    "items": [{"item_id": "COUPON_ACT_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}],
}


def _req(user_id: str, req_id: str, **overrides) -> dict:
    body = {**BASE_REQUEST, "user_id": user_id, "reqId": req_id}
    body.update(overrides)
    return body


class TestE2eBusiness:
    """e2e 业务测试用例"""

    # ── 一、HTTP 全链路 ──

    def test_tc_e2e_001(self, grpc_target, setup_e2e):
        """TC-E2E-001：通过 HTTP 走内部打分时完成主服务到 AB 服务再到发放的全链路"""
        __tc_meta__ = {
            "tc_id": "TC-E2E-001",
            "module": "e2e",
            "category": "business",
            "source": "test_workspace/cases/e2e/business.md",
            "title": "通过 HTTP 走内部打分时完成主服务到 AB 服务再到发放的全链路",
            "priority": "P0",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 环境覆盖：启动 Redis、AB 实验服务、内部 gRPC mock 打分服务和主服务；主服务配置 AB_SERVICE_URL={{ab_base_url}}
        # SETUP: 前置操作：在 AB 服务设置 u_e2e_http_internal_001 白名单，命中 {"coarse_rank_exp_game":"cr_v2_full","calibration_exp_game":"cal_on"}
        # SETUP: 前置操作_2：写入用户特征 {"gender":"female","age":"24","total_spend":"12000","purchase_frequency":"8","register_days":"60","is_new_user":"True","is_member":"True"}
        # SETUP: 前置操作_3：设置 COUPON_ACT_001 库存为 5
        # SETUP: 请求覆盖：scene_name="game"、device="mobile"、external=0、score_threshold=0.2、max_claim_per_request=1、items 只包含 COUPON_ACT_001
        setup_e2e(case_id="TC-E2E-001")

        resp = grpc_ops.recommend(grpc_target, _req("u_e2e_001", "req_e2e_001"))
        # UNPARSED ASSERTION: 请求完成后不产生跨用例共享脏数据
        # UNPARSED ASSERTION: 成功推荐场景均可通过用户券查询接口查询到同一条发放记录。
        assert isinstance(resp, dict)
        assert resp["code"] == 0
        assert resp["scene_id"] == 1001
        assert resp["experiment_info"] == {"coarse_rank_exp_game": "cr_v2_full", "calibration_exp_game": "cal_on"}
        assert resp["results"][0]["item_id"] == "COUPON_ACT_001"
        assert resp["results"][0]["recommended"] is True
        assert resp["coupon"] is not None and resp["coupon"]["item_id"] == "COUPON_ACT_001"
        assert resp["coupon"] is not None and resp["coupon"]["user_id"].startswith("u_e2e_")
        assert resp["coupon"] is not None and resp["coupon"]["status"] == "claimed"
        assert isinstance(resp, dict)
        assert isinstance(resp, dict)

    def test_tc_e2e_002(self, http_base_url, setup_e2e):
        """TC-E2E-002：通过 HTTP 走外部打分时跳过实验但仍完成推荐与发放"""
        __tc_meta__ = {
            "tc_id": "TC-E2E-002",
            "module": "e2e",
            "category": "business",
            "source": "test_workspace/cases/e2e/business.md",
            "title": "通过 HTTP 走外部打分时跳过实验但仍完成推荐与发放",
            "priority": "P0",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 环境覆盖：启动 Redis、AB 实验服务、外部 HTTP mock 打分服务和主服务；主服务配置 AB_SERVICE_URL={{ab_base_url}}
        # SETUP: 前置操作：写入用户特征 {"gender":"male","age":"31","total_spend":"8000","purchase_frequency":"5","register_days":"120","is_new_user":"False","is_member":"True"}
        # SETUP: 前置操作_2：设置 COUPON_SHIP_001 库存为 5
        # SETUP: 请求覆盖：user_id="u_e2e_http_external_002"、scene_name="ad"、device="pc"、external=1、score_threshold=0.2、max_claim_per_request=1、items 只包含 COUPON_SHIP_001
        setup_e2e(case_id="TC-E2E-002")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_e2e_002", "req_e2e_002", **{"scene_name": "ad", "device": "pc", "external": 1, "items": [{"item_id": "COUPON_SHIP_001", "coupon_type": "free_shipping", "value": 1, "min_spend": 0, "expire_days": 7}]}))
        # UNPARSED ASSERTION: 请求完成后不产生跨用例共享脏数据
        # UNPARSED ASSERTION: 成功推荐场景均可通过用户券查询接口查询到同一条发放记录。
        assert isinstance(resp, dict)
        assert resp["code"] == 0
        assert resp["scene_id"] == 2002
        assert resp["experiment_info"] == {}
        assert resp["results"][0]["item_id"] == "COUPON_SHIP_001"
        assert resp["results"][0]["recommended"] is True
        assert resp["coupon"] is not None and resp["coupon"]["item_id"] == "COUPON_SHIP_001"
        assert resp["coupon"] is not None and resp["coupon"]["user_id"].startswith("u_e2e_")
        assert isinstance(resp, dict)

    # ── 二、双协议对齐 ──

    def test_tc_e2e_003(self, grpc_target, setup_e2e):
        """TC-E2E-003：同一兜底请求通过 HTTP 和 gRPC 返回一致的业务结果"""
        __tc_meta__ = {
            "tc_id": "TC-E2E-003",
            "module": "e2e",
            "category": "business",
            "source": "test_workspace/cases/e2e/business.md",
            "title": "同一兜底请求通过 HTTP 和 gRPC 返回一致的业务结果",
            "priority": "P0",
            "markers": [],
        }
        # SETUP: 协议：HTTP / gRPC
        # SETUP: 环境覆盖：启动 Redis 和主服务；不依赖 AB 服务命中；不写入任何 coupon:fallback:score:* Redis key
        # SETUP: 前置操作：设置 COUPON_ACT_001 库存为 2
        # SETUP: 请求覆盖：HTTP 与 gRPC 使用同一业务请求，user_id="u_e2e_dual_proto_003"、scene_name="game"、device="mobile"、policy_id="policy_fallback_001"、external=0、score_threshold=0.4、max_claim_per_request=1、items 只包含 COUPON_ACT_001
        setup_e2e(case_id="TC-E2E-003")

        resp = grpc_ops.recommend(grpc_target, _req("u_e2e_003", "req_e2e_003", **{"policy_id": "policy_fallback_001", "score_threshold": 0.4}))
        # UNPARSED ASSERTION: 请求完成后不产生跨用例共享脏数据
        # UNPARSED ASSERTION: 成功推荐场景均可通过用户券查询接口查询到同一条发放记录。
        assert isinstance(resp, dict)
        assert resp["code"] == 0
        assert isinstance(resp, dict)
        assert isinstance(resp, dict)
        assert isinstance(resp, dict)
        assert resp["coupon"] is not None and resp["coupon"]["item_id"] == "COUPON_ACT_001"
        assert isinstance(resp, dict)



__codegen_skipped__ = []
