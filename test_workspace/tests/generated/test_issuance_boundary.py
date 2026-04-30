# Auto-generated from test_workspace/cases/issuance/boundary.md
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
    "score_threshold": 0.5,
    "max_claim_per_request": 1,
    "context": {},
    "items": [{"item_id": "COUPON_ISSUE_A", "coupon_type": "discount", "value": 100, "min_spend": 5000, "expire_days": 7}, {"item_id": "COUPON_ISSUE_B", "coupon_type": "fixed", "value": 80, "min_spend": 3000, "expire_days": 7}],
}


def _req(user_id: str, req_id: str, **overrides) -> dict:
    body = {**BASE_REQUEST, "user_id": user_id, "reqId": req_id}
    body.update(overrides)
    return body


class TestIssuanceBoundary:
    """issuance 边界测试用例"""

    # ── 一、库存边界 ──

    def test_tc_issue_011(self, setup_issuance):
        """TC-ISSUE-011：最高分券库存不足时尝试下一张券"""
        # SETUP: 协议：HTTP
        # SETUP: 前置操作：HTTP 探测请求传入 A/B 且库存均为 100，读取 top_item 与 second_item
        # SETUP: 前置操作_2：重置库存为 top_item=0、second_item=100
        # SETUP: 请求覆盖：验证请求 max_claim_per_request=2、score_threshold=0.0

        issue = setup_issuance(case_id="TC-ISSUE-011")
        issue.set_stock("COUPON_ISSUE_A", 0)
        issue.set_stock("COUPON_ISSUE_B", 100)
        body = issue.request(
            "u_issue_stock_next",
            "req_issue_011",
            items=issue_items("COUPON_ISSUE_A", "COUPON_ISSUE_B"),
            score_threshold=0.0,
            max_claim_per_request=2,
            policy_id="policy_fallback_001",
        )
        resp = issue.post_recommend(body)
        assert resp["code"] == 0
        assert resp["coupon"] is not None
        assert resp["coupon"]["item_id"] == "COUPON_ISSUE_B"
        assert issue.stock("COUPON_ISSUE_A") == 0

    def test_tc_issue_012(self, setup_issuance):
        """TC-ISSUE-012：所有候选券库存不足时返回成功但 coupon 为空"""
        # SETUP: 前置操作：A/B 库存均为 0
        # SETUP: 请求覆盖：max_claim_per_request=2、score_threshold=0.0

        issue = setup_issuance(case_id="TC-ISSUE-012")
        issue.set_stock("COUPON_ISSUE_A", 0)
        issue.set_stock("COUPON_ISSUE_B", 0)
        body = issue.request(
            "u_issue_all_empty",
            "req_issue_012",
            score_threshold=0.0,
            max_claim_per_request=2,
        )
        resp = issue.post_recommend(body)
        assert resp["code"] == 0
        assert resp["coupon"] is None
        assert resp["code"] != 1006

    def test_tc_issue_013(self, setup_issuance):
        """TC-ISSUE-013：并发请求同一库存只成功发放一次"""
        # SETUP: 前置操作：SET coupon:stock:COUPON_ISSUE_CONCURRENT 1 EX 86400
        # SETUP: 请求覆盖：两个不同 user_id 并发请求同一券
        # SETUP: 请求覆盖_2：score_threshold=0.0

        issue = setup_issuance(case_id="TC-ISSUE-013")
        issue.set_stock("COUPON_ISSUE_CONCURRENT", 1)
        body_a = issue.request(
            "u_issue_concurrent_a",
            "req_issue_013a",
            items=issue_items("COUPON_ISSUE_CONCURRENT"),
            score_threshold=0.0,
        )
        body_b = issue.request(
            "u_issue_concurrent_b",
            "req_issue_013b",
            items=issue_items("COUPON_ISSUE_CONCURRENT"),
            score_threshold=0.0,
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(issue.post_recommend, [body_a, body_b]))
        successes = [
            r for r in responses
            if r["coupon"] is not None and r["coupon"]["item_id"] == "COUPON_ISSUE_CONCURRENT"
        ]
        empty = [r for r in responses if r["coupon"] is None]
        assert all(r["code"] == 0 for r in responses)
        assert len(successes) == 1
        assert len(empty) == 1
        assert issue.stock("COUPON_ISSUE_CONCURRENT") == 0

    # ── 二、输入边界 ──

    def test_tc_issue_016(self, setup_issuance):
        """TC-ISSUE-016：expire_days 缺省时 HTTP item 默认值为 7 天"""
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 item 省略 expire_days，其他字段完整
        # SETUP: 请求覆盖_2：成功发放

        issue = setup_issuance(case_id="TC-ISSUE-016")
        body = issue.request(
            "u_issue_default_expire",
            "req_issue_016",
            items=[issue_item("COUPON_ISSUE_A", expire_days=None)],
            score_threshold=0.0,
        )
        resp = issue.post_recommend(body)
        assert resp["code"] == 0
        assert resp["coupon"] is not None
        assert resp["coupon"]["expire_time"] - resp["coupon"]["claim_time"] == 7 * 86400

    def test_tc_issue_017(self, setup_issuance):
        """TC-ISSUE-017：max_claim_per_request 大于候选数时最多尝试全部候选"""
        # SETUP: 协议：HTTP
        # SETUP: 前置操作：HTTP 探测请求传入 A/B 且库存均为 100，读取 top_item 与 second_item
        # SETUP: 前置操作_2：重置库存为 top_item=0、second_item=100
        # SETUP: 请求覆盖：验证请求 max_claim_per_request=10、score_threshold=0.0

        issue = setup_issuance(case_id="TC-ISSUE-017")
        issue.set_stock("COUPON_ISSUE_A", 0)
        issue.set_stock("COUPON_ISSUE_B", 100)
        body = issue.request(
            "u_issue_max_gt_count",
            "req_issue_017",
            items=issue_items("COUPON_ISSUE_A", "COUPON_ISSUE_B"),
            score_threshold=0.0,
            max_claim_per_request=10,
            policy_id="policy_fallback_001",
        )
        resp = issue.post_recommend(body)
        assert resp["code"] == 0
        assert resp["coupon"] is not None
        assert resp["coupon"]["item_id"] == "COUPON_ISSUE_B"

    def test_tc_issue_018(self, setup_issuance):
        """TC-ISSUE-018：gRPC 最高分券库存不足时尝试下一张券"""
        # SETUP: 协议：gRPC
        # SETUP: 前置操作：gRPC 探测请求传入 A/B 且库存均为 100，读取 top_item 与 second_item
        # SETUP: 前置操作_2：重置库存为 top_item=0、second_item=100
        # SETUP: 请求覆盖：验证请求 max_claim_per_request=2、score_threshold=0.0

        issue = setup_issuance(case_id="TC-ISSUE-018")
        issue.set_stock("COUPON_ISSUE_A", 0)
        issue.set_stock("COUPON_ISSUE_B", 100)
        body = issue.request(
            "u_issue_grpc_stock_next",
            "req_issue_018",
            items=issue_items("COUPON_ISSUE_A", "COUPON_ISSUE_B"),
            score_threshold=0.0,
            max_claim_per_request=2,
            policy_id="policy_fallback_001",
        )
        resp = issue.grpc_recommend(body)
        assert resp["code"] == 0
        assert resp["coupon"] is not None
        assert resp["coupon"]["item_id"] == "COUPON_ISSUE_B"
        assert issue.stock("COUPON_ISSUE_A") == 0

    def test_tc_issue_019(self, setup_issuance):
        """TC-ISSUE-019：gRPC 所有候选券库存不足时返回成功但 coupon 为空"""
        # SETUP: 协议：gRPC
        # SETUP: 前置操作：gRPC 请求传入 A/B，库存均为 0
        # SETUP: 请求覆盖：max_claim_per_request=2、score_threshold=0.0

        issue = setup_issuance(case_id="TC-ISSUE-019")
        issue.set_stock("COUPON_ISSUE_A", 0)
        issue.set_stock("COUPON_ISSUE_B", 0)
        body = issue.request(
            "u_issue_grpc_all_empty",
            "req_issue_019",
            score_threshold=0.0,
            max_claim_per_request=2,
        )
        resp = issue.grpc_recommend(body)
        assert resp["code"] == 0
        assert resp["coupon"] is None
        assert resp["code"] != 1006

    def test_tc_issue_020(self, setup_issuance):
        """TC-ISSUE-020：gRPC max_claim_per_request 大于候选数时不报错"""
        # SETUP: 协议：gRPC
        # SETUP: 前置操作：gRPC 请求传入两张库存充足的候选券
        # SETUP: 请求覆盖：max_claim_per_request=10、score_threshold=0.0

        issue = setup_issuance(case_id="TC-ISSUE-020")
        body = issue.request(
            "u_issue_grpc_max_gt_count",
            "req_issue_020",
            score_threshold=0.0,
            max_claim_per_request=10,
        )
        resp = issue.grpc_recommend(body)
        assert resp["code"] == 0
        assert resp["coupon"] is None or resp["coupon"]["item_id"] in {r["item_id"] for r in resp["results"]}


# SKIPPED: TC-ISSUE-014 — `[!可行性存疑: L1 未规定去重限制，当前实现未调用 has_claimed，需产品确认是否允许重复领取]`
# SKIPPED: TC-ISSUE-015 — `[!可行性存疑: 需要测试环境能在扣库存后注入 Redis 写失败]`
