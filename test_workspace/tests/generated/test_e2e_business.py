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

    def test_tc_e2e_001(self, setup_e2e):
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

        e2e = setup_e2e(case_id="TC-E2E-001")
        e2e.set_stock("COUPON_ACT_001", 5)
        body = e2e.request("u_e2e_http_internal_001", "req_e2e_001")
        response = e2e.post_recommend_response(body)
        assert response.status_code == 200
        resp = response.json()
        coupons = e2e.query_coupons("u_e2e_http_internal_001")
        assert resp["code"] == 0
        assert resp["scene_id"] == 1001
        assert resp["experiment_info"] == {"coarse_rank_exp_game": "cr_v2_full", "calibration_exp_game": "cal_on"}
        assert resp["results"][0]["item_id"] == "COUPON_ACT_001"
        assert resp["results"][0]["recommended"] is True
        assert resp["coupon"] is not None
        assert resp["coupon"]["item_id"] == "COUPON_ACT_001"
        assert resp["coupon"]["user_id"] == "u_e2e_http_internal_001"
        assert resp["coupon"]["status"] == "claimed"
        assert e2e.stock("COUPON_ACT_001") == 4
        assert coupons["total"] == 1
        assert coupons["coupons"][0]["instance_id"] == resp["coupon"]["instance_id"]

    def test_tc_e2e_002(self, setup_e2e):
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

        e2e = setup_e2e(case_id="TC-E2E-002")
        e2e.set_stock("COUPON_SHIP_001", 5)
        body = e2e.request("u_e2e_http_external_002", "req_e2e_002", coupon_id="COUPON_SHIP_001", scene_name="ad", device="pc", external=1)
        response = e2e.post_recommend_response(body)
        assert response.status_code == 200
        resp = response.json()
        coupons = e2e.query_coupons("u_e2e_http_external_002")
        assert resp["code"] == 0
        assert resp["scene_id"] == 2002
        assert resp["experiment_info"] == {}
        assert resp["results"][0]["item_id"] == "COUPON_SHIP_001"
        assert resp["results"][0]["recommended"] is True
        assert resp["coupon"] is not None
        assert resp["coupon"]["item_id"] == "COUPON_SHIP_001"
        assert resp["coupon"]["user_id"] == "u_e2e_http_external_002"
        assert coupons["total"] == 1
        assert coupons["coupons"][0]["item_id"] == "COUPON_SHIP_001"

    # ── 二、双协议对齐 ──

    def test_tc_e2e_003(self, setup_e2e):
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

        e2e = setup_e2e(case_id="TC-E2E-003")
        e2e.set_stock("COUPON_ACT_001", 2)
        body = e2e.request("u_e2e_dual_proto_003", "req_e2e_003", policy_id="policy_fallback_001", score_threshold=0.4)
        http_response = e2e.post_recommend_response(body)
        assert http_response.status_code == 200
        http_json = http_response.json()
        grpc_resp = e2e.grpc_recommend(body)
        assert http_json["code"] == 0
        assert grpc_resp["code"] == 0
        assert http_json["scene_id"] == 3001
        assert grpc_resp["scene_id"] == 3001
        assert http_json["experiment_info"] == {}
        assert grpc_resp["experiment_info"] == {}
        assert http_json["results"][0]["item_id"] == "COUPON_ACT_001"
        assert grpc_resp["results"][0]["item_id"] == "COUPON_ACT_001"
        assert http_json["results"][0]["score"] == 0.5
        assert grpc_resp["results"][0]["score"] == 0.5
        assert http_json["results"][0]["calibrated_score"] == 0.5
        assert grpc_resp["results"][0]["calibrated_score"] == 0.5
        assert http_json["results"][0]["recommended"] is True
        assert grpc_resp["results"][0]["recommended"] is True
        assert http_json["coupon"]["item_id"] == "COUPON_ACT_001"
        assert grpc_resp["coupon"]["item_id"] == "COUPON_ACT_001"
        assert e2e.stock("COUPON_ACT_001") == 0



__codegen_skipped__ = []
