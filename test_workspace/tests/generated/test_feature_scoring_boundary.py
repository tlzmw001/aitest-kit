# Auto-generated from test_workspace/cases/feature_scoring/boundary.md
# DO NOT EDIT — regenerate with: /test-codegen feature_scoring
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
    "items": [{"item_id": "{{item_id}}", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}],
}


def _req(user_id: str, req_id: str, **overrides) -> dict:
    body = {**BASE_REQUEST, "user_id": user_id, "reqId": req_id}
    body.update(overrides)
    return body


class TestFeatureScoringBoundary:
    """feature_scoring 边界测试用例"""

    # ── 一、Redis 特征读取边界 ──

    @pytest.mark.manual
    def test_tc_feat_004(self, http_base_url, setup_feature_scoring):
        """TC-FEAT-004：用户特征 key 不存在时静默省略"""
        # SETUP: 协议：HTTP
        # SETUP: 前置操作：删除用户全部特征 key：DEL coupon:user_feature:gender:u_feat_missing ...
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_feat_missing"、item_id="COUPON_FEAT_MISSING"
        setup_feature_scoring(case_id="TC-FEAT-004")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_feat_missing", "req_feat_004", **{"items": [{"item_id": "COUPON_FEAT_MISSING", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}]}))
        # MANUAL CHECK: response.body.code == 0
        # MANUAL CHECK: 打分服务收到的 user_features == {}

    # ── 二、Item 特征文件降级 ──

    @pytest.mark.manual
    def test_tc_feat_006(self, http_base_url, setup_feature_scoring):
        """TC-FEAT-006：TSV 文件不存在时安全降级为空 item 特征"""
        # SETUP: 协议：HTTP
        # SETUP: 环境覆盖：使用独立测试配置启动服务，item_feature_file="/tmp/not_exists_item_features.tsv"
        # SETUP: 请求覆盖：HTTP 请求 item_id="COUPON_FEAT_NO_FILE"
        setup_feature_scoring(case_id="TC-FEAT-006")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_feat_no_file", "req_feat_006", **{"items": [{"item_id": "COUPON_FEAT_NO_FILE", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}]}))
        # MANUAL CHECK: response.body.code == 0
        # MANUAL CHECK: 应用日志包含 item 特征文件不存在

    @pytest.mark.manual
    def test_tc_feat_007(self, http_base_url, setup_feature_scoring):
        """TC-FEAT-007：TSV 行格式错误时跳过该行"""
        # SETUP: 协议：HTTP
        # SETUP: 前置操作：测试 TSV 内容包含一行 BAD_LINE_WITHOUT_TAB 和一行合法 COUPON_FEAT_OK\t{"brand":"A"}
        # SETUP: 请求覆盖：HTTP 请求 item_id="COUPON_FEAT_OK"
        setup_feature_scoring(case_id="TC-FEAT-007")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_feat_ok", "req_feat_007", **{"items": [{"item_id": "COUPON_FEAT_OK", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}]}))
        # MANUAL CHECK: response.body.code == 0
        # MANUAL CHECK: 日志包含 item 特征文件第 1 行格式错误

    @pytest.mark.manual
    def test_tc_feat_008(self, http_base_url, setup_feature_scoring):
        """TC-FEAT-008：TSV JSON 解析失败时跳过该行"""
        # SETUP: 协议：HTTP
        # SETUP: 前置操作：测试 TSV 内容包含 COUPON_FEAT_BAD\t{bad json
        # SETUP: 请求覆盖：HTTP 请求 item_id="COUPON_FEAT_BAD"
        setup_feature_scoring(case_id="TC-FEAT-008")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_feat_bad", "req_feat_008", **{"items": [{"item_id": "COUPON_FEAT_BAD", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}]}))
        # MANUAL CHECK: response.body.code == 0
        # MANUAL CHECK: 日志包含 JSON 解析失败

    def test_tc_feat_009(self, http_base_url, setup_feature_scoring):
        """TC-FEAT-009：不存在的 item 返回空特征但 pipeline 不中断"""
        # SETUP: 协议：HTTP
        # SETUP: 前置操作：HTTP 请求 item_id="COUPON_FEAT_NOT_IN_TSV"，该 item 不在 TSV 中
        setup_feature_scoring(case_id="TC-FEAT-009")

        resp = http_helper.post(http_base_url, "/api/v1/recommend", json=_req("u_feat_not_in_tsv", "req_feat_009", **{"items": [{"item_id": "COUPON_FEAT_NOT_IN_TSV", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}]}))
        assert resp["code"] == 0
        assert resp["code"] == 0
        assert resp["results"][0]["item_id"] == "COUPON_FEAT_NOT_IN_TSV"


# SKIPPED: TC-FEAT-005 — `[!可行性存疑: 需要测试环境允许控制 Redis 可用性]`
# SKIPPED: TC-SCORE-006 — `[!可行性存疑: 当前集成环境的内部 gRPC mock 打分服务没有公开控制接口可按用例触发超时]`
# SKIPPED: TC-SCORE-007 — `[!可行性存疑: 当前集成环境的内部 gRPC mock 打分服务没有公开控制接口可按用例触发不可用]`
# SKIPPED: TC-SCORE-008 — `[!可行性存疑: 需要测试环境支持独立 fallback 配置启动服务]`
# SKIPPED: TC-SCORE-009 — `[!可行性存疑: 当前集成环境的内部 gRPC mock 打分服务没有公开控制接口可按用例触发 RuntimeError]`
