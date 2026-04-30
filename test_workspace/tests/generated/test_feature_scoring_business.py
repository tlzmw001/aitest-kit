# Auto-generated from test_workspace/cases/feature_scoring/business.md
# DO NOT EDIT — regenerate with: /test-codegen feature_scoring
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
    "context": {
        "channel": "test",
    },
    "items": [{"item_id": "COUPON_FEAT_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}],
}


def _req(user_id: str, req_id: str, **overrides) -> dict:
    body = {**BASE_REQUEST, "user_id": user_id, "reqId": req_id}
    body.update(overrides)
    return body


class TestFeatureScoringBusiness:
    """feature_scoring 业务测试用例"""

    # ── 一、特征抽取 ──

    @pytest.mark.manual
    def test_tc_feat_001(self, http_base_url, setup_feature_scoring):
        """TC-FEAT-001：HTTP 读取 Redis 用户特征并透传给打分"""
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_feat_http"、external=0
        # SETUP: 前置操作：Redis 设置 gender=male、total_spend=1200
        setup_feature_scoring(case_id="TC-FEAT-001")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_feat_http", "req_feat_001", **{"external": 0}))
        # MANUAL CHECK: response.body.code == 0
        # MANUAL CHECK: 打分服务收到的 user_features 包含 gender="male"、total_spend="1200"

    @pytest.mark.manual
    def test_tc_feat_002(self, grpc_target, setup_feature_scoring):
        """TC-FEAT-002：gRPC 读取 Redis 用户特征并透传给打分"""
        # SETUP: 协议：gRPC
        # SETUP: 请求覆盖：gRPC 请求 user_id="u_feat_grpc"、external=0
        # SETUP: 前置操作：Redis 设置 age=30、is_member=true
        setup_feature_scoring(case_id="TC-FEAT-002")

        resp = grpc_ops.recommend(grpc_target, _req("u_feat_grpc", "req_feat_002", **{"external": 0}))
        # MANUAL CHECK: response.code == 0
        # MANUAL CHECK: 打分服务收到的 user_features 包含 age="30"、is_member="true"

    @pytest.mark.manual
    def test_tc_feat_003(self, http_base_url, setup_feature_scoring):
        """TC-FEAT-003：请求 item 字段与 TSV item 特征合并后进入打分"""
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 item 为 COUPON_FEAT_001，请求体包含 coupon_type="discount"、value=80、min_spend=5000、expire_days=7
        # SETUP: 前置操作：TSV 中存在该 item 的其他特征
        setup_feature_scoring(case_id="TC-FEAT-003")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_feat_item_merge", "req_feat_003", **{"external": 0, "items": [{"item_id": "COUPON_FEAT_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}]}))
        # MANUAL CHECK: 打分服务收到的 item features 同时包含 TSV 特征和请求体中的 coupon_type/value/min_spend/expire_days

    # ── 二、打分路由 ──

    @pytest.mark.manual
    def test_tc_score_001(self, http_base_url, setup_feature_scoring):
        """TC-SCORE-001：HTTP external=0 调用内部 gRPC 打分"""
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_score_internal_http"、external=0、reqId="req-score-001"
        setup_feature_scoring(case_id="TC-SCORE-001")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_score_internal_http", "req-score-001", **{"external": 0}))
        # MANUAL CHECK: response.body.code == 0
        # MANUAL CHECK: response.body.results[0].score >= 0.1
        # MANUAL CHECK: 内部打分服务收到明文 user_id="u_score_internal_http"

    @pytest.mark.manual
    def test_tc_score_002(self, grpc_target, setup_feature_scoring):
        """TC-SCORE-002：gRPC external=0 调用内部 gRPC 打分"""
        # SETUP: 协议：gRPC
        # SETUP: 请求覆盖：gRPC 请求 user_id="u_score_internal_grpc"、external=0、req_id="req-score-002"
        setup_feature_scoring(case_id="TC-SCORE-002")

        resp = grpc_ops.recommend(grpc_target, _req("u_score_internal_grpc", "req-score-002", **{"external": 0}))
        # MANUAL CHECK: response.code == 0
        # MANUAL CHECK: response.results[0].score >= 0.1
        # MANUAL CHECK: 内部打分服务收到明文 user_id="u_score_internal_grpc"

    def test_tc_score_003(self, http_base_url, setup_feature_scoring):
        """TC-SCORE-003：HTTP external=1 调用外部 HTTP 打分"""
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_score_external_http"、external=1、reqId="req-score-003"
        setup_feature_scoring(case_id="TC-SCORE-003")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_score_external_http", "req-score-003", **{"external": 1}))
        assert resp["code"] == 0
        assert resp["code"] == 0
        assert resp["results"][0]["score"] >= 0.2
        assert resp["experiment_info"] == {}

    def test_tc_score_004(self, grpc_target, setup_feature_scoring):
        """TC-SCORE-004：gRPC external=1 调用外部 HTTP 打分"""
        # SETUP: 协议：gRPC
        # SETUP: 请求覆盖：gRPC 请求 user_id="u_score_external_grpc"、external=1、req_id="req-score-004"
        setup_feature_scoring(case_id="TC-SCORE-004")

        resp = grpc_ops.recommend(grpc_target, _req("u_score_external_grpc", "req-score-004", **{"external": 1}))
        assert resp["code"] == 0
        assert resp["code"] == 0
        assert resp["results"][0]["score"] >= 0.2
        assert resp["experiment_info"] == {}

    @pytest.mark.manual
    def test_tc_score_005(self, http_base_url, setup_feature_scoring):
        """TC-SCORE-005：外部打分 user_id 使用加盐 SHA-256"""
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_score_encrypt"、external=1
        # SETUP: 请求覆盖_2：外部打分服务 salt 使用默认 coupon_external_uid_salt
        setup_feature_scoring(case_id="TC-SCORE-005")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_score_encrypt", "req_feat_005", **{"external": 1}))
        # MANUAL CHECK: 外部打分服务收到的 user_id == sha256("coupon_external_uid_salt:u_score_encrypt")
        # MANUAL CHECK: 不包含明文 u_score_encrypt


