# Auto-generated from test_workspace/cases/issuance/business.md
# DO NOT EDIT — regenerate with: /test-codegen issuance
import pytest
from test_workspace.tests.helpers import http as http_helper
from test_workspace.tests.helpers import grpc_ops
from concurrent.futures import ThreadPoolExecutor
from test_workspace.tests.fixtures.issuance import issue_item, issue_items


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
    "items": [{"item_id": "COUPON_ISSUE_A", "coupon_type": "discount", "value": 100, "min_spend": 5000, "expire_days": 7}, {"item_id": "COUPON_ISSUE_B", "coupon_type": "fixed", "value": 80, "min_spend": 3000, "expire_days": 7}],
}


def _req(user_id: str, req_id: str, **overrides) -> dict:
    body = {**BASE_REQUEST, "user_id": user_id, "reqId": req_id}
    body.update(overrides)
    return body


class TestIssuanceBusiness:
    """issuance 业务测试用例"""

    # ── 一、发放选择 ──

    def test_tc_issue_001(self, setup_issuance):
        """TC-ISSUE-001：HTTP 正常发放最高分券"""
        # SETUP: 协议：HTTP
        # SETUP: 前置操作：HTTP 请求 user_id="u_issue_http_ok"，两张券库存均为 100
        # SETUP: 请求覆盖：score_threshold=0.0、max_claim_per_request=1

        issue = setup_issuance(case_id="TC-ISSUE-001")
        body = issue.request(
            "u_issue_http_ok",
            "req_issue_001",
            score_threshold=0.0,
            max_claim_per_request=1,
        )
        resp = issue.post_recommend(body)
        assert resp["code"] == 0
        assert resp["coupon"] is not None
        assert resp["coupon"]["item_id"] == max(resp["results"], key=lambda r: r["score"])["item_id"]
        assert resp["coupon"]["user_id"] == "u_issue_http_ok"
        assert resp["coupon"]["status"] == "claimed"

    def test_tc_issue_002(self, setup_issuance):
        """TC-ISSUE-002：gRPC 正常发放最高分券"""
        # SETUP: 协议：gRPC
        # SETUP: 前置操作：gRPC 请求 user_id="u_issue_grpc_ok"，两张券库存均为 100
        # SETUP: 请求覆盖：score_threshold=0.0、max_claim_per_request=1

        issue = setup_issuance(case_id="TC-ISSUE-002")
        body = issue.request(
            "u_issue_grpc_ok",
            "req_issue_002",
            score_threshold=0.0,
            max_claim_per_request=1,
        )
        resp = issue.grpc_recommend(body)
        assert resp["code"] == 0
        assert resp["coupon"] is not None
        assert resp["coupon"]["item_id"] == max(resp["results"], key=lambda r: r["score"])["item_id"]
        assert resp["coupon"]["user_id"] == "u_issue_grpc_ok"
        assert resp["coupon"]["status"] == "claimed"

    def test_tc_issue_003(self, setup_issuance):
        """TC-ISSUE-003：score_threshold 等于分数上界时不发放"""
        # SETUP: 协议：HTTP
        # SETUP: 前置操作：HTTP 请求 user_id="u_issue_high_threshold"，两张券库存均为 100
        # SETUP: 请求覆盖：score_threshold=1.0

        issue = setup_issuance(case_id="TC-ISSUE-003")
        body = issue.request(
            "u_issue_high_threshold",
            "req_issue_003",
            score_threshold=1.0,
            max_claim_per_request=1,
        )
        resp = issue.post_recommend(body)
        assert resp["code"] == 0
        assert resp["coupon"] is None
        assert all(not r["recommended"] for r in resp["results"])

    # ── 二、库存与查询 ──

    def test_tc_issue_004(self, setup_issuance):
        """TC-ISSUE-004：发放成功后库存扣减 1"""
        # SETUP: 协议：HTTP
        # SETUP: 前置操作：SET coupon:stock:COUPON_ISSUE_A 2 EX 86400
        # SETUP: 请求覆盖：HTTP 请求只传 A
        # SETUP: 请求覆盖_2：score_threshold=0.0

        issue = setup_issuance(case_id="TC-ISSUE-004")
        issue.set_stock("COUPON_ISSUE_A", 2)
        before = issue.stock("COUPON_ISSUE_A")
        body = issue.request(
            "u_issue_stock_decr",
            "req_issue_004",
            items=issue_items("COUPON_ISSUE_A"),
            score_threshold=0.0,
        )
        resp = issue.post_recommend(body)
        after = issue.stock("COUPON_ISSUE_A")
        assert resp["code"] == 0
        assert resp["coupon"] is not None
        assert resp["coupon"]["item_id"] == "COUPON_ISSUE_A"
        assert before == 2
        assert after == 1

    def test_tc_issue_005(self, setup_issuance):
        """TC-ISSUE-005：发放记录可通过用户券查询接口查到"""
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_issue_query" 成功发放 A

        issue = setup_issuance(case_id="TC-ISSUE-005")
        body = issue.request(
            "u_issue_query",
            "req_issue_005",
            items=issue_items("COUPON_ISSUE_A"),
            score_threshold=0.0,
        )
        resp = issue.post_recommend(body)
        query = issue.query_coupons("u_issue_query")
        assert resp["code"] == 0
        assert resp["coupon"] is not None
        assert query["code"] == 0
        assert query["total"] >= 1
        assert "COUPON_ISSUE_A" in {c["item_id"] for c in query["coupons"]}

    def test_tc_issue_006(self, setup_issuance):
        """TC-ISSUE-006：coupon 过期时间按 expire_days 计算"""
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 item A 的 expire_days=3，成功发放

        issue = setup_issuance(case_id="TC-ISSUE-006")
        body = issue.request(
            "u_issue_expire_3",
            "req_issue_006",
            items=[issue_item("COUPON_ISSUE_A", expire_days=3)],
            score_threshold=0.0,
        )
        resp = issue.post_recommend(body)
        assert resp["code"] == 0
        assert resp["coupon"] is not None
        assert resp["coupon"]["expire_time"] - resp["coupon"]["claim_time"] == 3 * 86400

    # ── 三、请求级控制 ──

    def test_tc_issue_007(self, setup_issuance):
        """TC-ISSUE-007：score_threshold 请求参数控制是否推荐"""
        # SETUP: 前置操作：同一用户隔离请求，只传 COUPON_ISSUE_A 且库存为 100
        # SETUP: 请求覆盖：第一次 score_threshold=1.0，第二次 score_threshold=0.0

        issue = setup_issuance(case_id="TC-ISSUE-007")
        first = issue.post_recommend(issue.request(
            "u_issue_threshold_control",
            "req_issue_007a",
            items=issue_items("COUPON_ISSUE_A"),
            score_threshold=1.0,
        ))
        second = issue.post_recommend(issue.request(
            "u_issue_threshold_control",
            "req_issue_007b",
            items=issue_items("COUPON_ISSUE_A"),
            score_threshold=0.0,
        ))
        assert first["code"] == 0
        assert first["coupon"] is None
        assert second["code"] == 0
        assert second["coupon"] is not None
        assert second["coupon"]["item_id"] == "COUPON_ISSUE_A"

    def test_tc_issue_008(self, setup_issuance):
        """TC-ISSUE-008：max_claim_per_request 控制尝试发放数量"""
        # SETUP: 请求覆盖：先用同一 user_id 和 A/B 候选发送探测请求，按响应 results[*].score 得到 top_item 与 second_item
        # SETUP: 前置操作：清理探测用户领取记录并重置库存后，设置 top_item 库存为 0、second_item 库存为 100
        # SETUP: 请求覆盖_2：第一次 max_claim_per_request=1，第二次 max_claim_per_request=2，两次 score_threshold=0.0

        issue = setup_issuance(case_id="TC-ISSUE-008")
        issue.set_stock("COUPON_ISSUE_A", 0)
        issue.set_stock("COUPON_ISSUE_B", 100)
        first = issue.post_recommend(issue.request(
            "u_issue_max_claim",
            "req_issue_008a",
            items=issue_items("COUPON_ISSUE_A", "COUPON_ISSUE_B"),
            score_threshold=0.0,
            max_claim_per_request=1,
            policy_id="policy_fallback_001",
        ))
        second = issue.post_recommend(issue.request(
            "u_issue_max_claim",
            "req_issue_008b",
            items=issue_items("COUPON_ISSUE_A", "COUPON_ISSUE_B"),
            score_threshold=0.0,
            max_claim_per_request=2,
            policy_id="policy_fallback_001",
        ))
        assert first["code"] == 0
        assert first["coupon"] is None
        assert second["code"] == 0
        assert second["coupon"] is not None
        assert second["coupon"]["item_id"] == "COUPON_ISSUE_B"

    # ── 四、查询接口 ──

    def test_tc_issue_009(self, setup_issuance):
        """TC-ISSUE-009：未领券用户查询返回空列表"""
        # SETUP: 接口调用：调用 GET /api/v1/coupons/user_no_coupons，该用户没有领取记录

        issue = setup_issuance(case_id="TC-ISSUE-009")
        issue.cleanup_user("user_no_coupons")
        resp = issue.query_coupons("user_no_coupons")
        assert resp["code"] == 0
        assert resp["coupons"] == []
        assert resp["total"] == 0

    def test_tc_issue_010(self, setup_issuance):
        """TC-ISSUE-010：查询接口 user_id 为空返回参数错误"""
        # SETUP: 协议：gRPC
        # SETUP: 请求覆盖：通过 gRPC 或业务层查询接口传入 user_id=""

        issue = setup_issuance(case_id="TC-ISSUE-010")
        resp = issue.grpc_query_coupons("")
        assert resp["code"] == 1001
        assert resp["message"] == "user_id不能为空"
        assert resp["coupons"] == []
        assert resp["total"] == 0


