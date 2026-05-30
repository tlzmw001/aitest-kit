# Auto-generated from test_workspace/suites/discount_system/discount_policy_smoke/business.md
# DO NOT EDIT — regenerate with: aitest codegen --suite-file test_workspace/suites/discount_system/discount_policy_smoke/suite.yaml
import pytest
from aitest_kit.helpers import http as http_helper
from test_workspace.targets.discount_system.fixtures.discount_policy import setup_discount_policy


BASE_REQUEST = {
    "user_id": None,
    "user_level": "normal",
    "item_id": "item_dp_default",
    "item_price": 120.5,
    "scene": "checkout",
    "stock": 5,
    "request_id": "req_dp_default",
}


def _req(**overrides) -> dict:
    body = {**BASE_REQUEST}
    body.update(overrides)
    return body


class TestDiscountPolicyBusiness:
    """discount_policy 业务测试用例"""

    # ── 一、健康检查与规则优先级 ──

    def test_tc_dp_001(self, setup_discount_policy):
        """TC-DP-001：健康检查返回 ok"""
        __tc_meta__ = {
            "tc_id": "TC-DP-001",
            "module": "discount_policy",
            "category": "business",
            "source": "test_workspace/suites/discount_system/discount_policy_smoke/business.md",
            "title": "健康检查返回 ok",
            "priority": "P0",
            "markers": [],
        }
        # SETUP: 接口调用：GET /health

        dp = setup_discount_policy
        dp = setup_discount_policy(case_id="TC-DP-001")
        resp = dp.health()
        assert resp.status_code == 200
        body = resp.json()
        assert body == {'status': 'ok'}

    def test_tc_dp_002(self, setup_discount_policy):
        """TC-DP-002：黑名单用户优先于活动和库存"""
        __tc_meta__ = {
            "tc_id": "TC-DP-002",
            "module": "discount_policy",
            "category": "business",
            "source": "test_workspace/suites/discount_system/discount_policy_smoke/business.md",
            "title": "黑名单用户优先于活动和库存",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 请求覆盖：{"user_id": "u_dp_002", "user_level": "black", "scene": "campaign", "stock": 0, "request_id": "req_dp_002"}

        dp = setup_discount_policy
        dp = setup_discount_policy(case_id="TC-DP-002")
        payload = dp.payload(user_id="u_dp_002", user_level="black", scene="campaign", stock=0, request_id="req_dp_002")
        resp = dp.evaluate(payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["eligible"] is False
        assert body["discount_rate"] == pytest.approx(1.0)
        assert body["reason_code"] == "USER_BLOCKED"
        assert body["request_id"] == "req_dp_002"

    def test_tc_dp_003(self, setup_discount_policy):
        """TC-DP-003：库存为空优先于活动规则"""
        __tc_meta__ = {
            "tc_id": "TC-DP-003",
            "module": "discount_policy",
            "category": "business",
            "source": "test_workspace/suites/discount_system/discount_policy_smoke/business.md",
            "title": "库存为空优先于活动规则",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 请求覆盖：{"user_id": "u_dp_003", "user_level": "vip", "scene": "campaign", "stock": 0, "request_id": "req_dp_003"}

        dp = setup_discount_policy
        dp = setup_discount_policy(case_id="TC-DP-003")
        payload = dp.payload(user_id="u_dp_003", user_level="vip", scene="campaign", stock=0, request_id="req_dp_003")
        resp = dp.evaluate(payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["eligible"] is False
        assert body["discount_rate"] == pytest.approx(1.0)
        assert body["reason_code"] == "STOCK_EMPTY"
        assert body["request_id"] == "req_dp_003"

    def test_tc_dp_004(self, setup_discount_policy):
        """TC-DP-004：活动场景命中八折"""
        __tc_meta__ = {
            "tc_id": "TC-DP-004",
            "module": "discount_policy",
            "category": "business",
            "source": "test_workspace/suites/discount_system/discount_policy_smoke/business.md",
            "title": "活动场景命中八折",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 请求覆盖：{"user_id": "u_dp_004", "user_level": "normal", "scene": "campaign", "stock": 5, "request_id": "req_dp_004"}

        dp = setup_discount_policy
        dp = setup_discount_policy(case_id="TC-DP-004")
        payload = dp.payload(user_id="u_dp_004", user_level="normal", scene="campaign", stock=5, request_id="req_dp_004")
        resp = dp.evaluate(payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["eligible"] is True
        assert body["discount_rate"] == pytest.approx(0.8)
        assert body["reason_code"] == "CAMPAIGN"
        assert body["request_id"] == "req_dp_004"

    def test_tc_dp_005(self, setup_discount_policy):
        """TC-DP-005：VIP 结算命中九折"""
        __tc_meta__ = {
            "tc_id": "TC-DP-005",
            "module": "discount_policy",
            "category": "business",
            "source": "test_workspace/suites/discount_system/discount_policy_smoke/business.md",
            "title": "VIP 结算命中九折",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 请求覆盖：{"user_id": "u_dp_005", "user_level": "vip", "scene": "checkout", "stock": 5, "request_id": "req_dp_005"}

        dp = setup_discount_policy
        dp = setup_discount_policy(case_id="TC-DP-005")
        payload = dp.payload(user_id="u_dp_005", user_level="vip", scene="checkout", stock=5, request_id="req_dp_005")
        resp = dp.evaluate(payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["eligible"] is True
        assert body["discount_rate"] == pytest.approx(0.9)
        assert body["reason_code"] == "VIP_CHECKOUT"
        assert body["request_id"] == "req_dp_005"

    def test_tc_dp_006(self, setup_discount_policy):
        """TC-DP-006：普通结算走默认规则"""
        __tc_meta__ = {
            "tc_id": "TC-DP-006",
            "module": "discount_policy",
            "category": "business",
            "source": "test_workspace/suites/discount_system/discount_policy_smoke/business.md",
            "title": "普通结算走默认规则",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 请求覆盖：{"user_id": "u_dp_006", "user_level": "normal", "scene": "checkout", "stock": 5, "request_id": "req_dp_006"}

        dp = setup_discount_policy
        dp = setup_discount_policy(case_id="TC-DP-006")
        payload = dp.payload(user_id="u_dp_006", user_level="normal", scene="checkout", stock=5, request_id="req_dp_006")
        resp = dp.evaluate(payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["eligible"] is True
        assert body["discount_rate"] == pytest.approx(1.0)
        assert body["reason_code"] == "DEFAULT"
        assert body["request_id"] == "req_dp_006"

    # ── 二、决策生命周期 ──

    def test_tc_dp_007(self, setup_discount_policy):
        """TC-DP-007：成功评估后可按 request_id 查询"""
        __tc_meta__ = {
            "tc_id": "TC-DP-007",
            "module": "discount_policy",
            "category": "business",
            "source": "test_workspace/suites/discount_system/discount_policy_smoke/business.md",
            "title": "成功评估后可按 request_id 查询",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 接口调用：先 POST /api/v1/discount/policy，再 GET /api/v1/discount/decisions/req_dp_007
        # SETUP: 请求覆盖：{"user_id": "u_dp_007", "user_level": "vip", "scene": "checkout", "stock": 5, "request_id": "req_dp_007"}

        dp = setup_discount_policy
        dp = setup_discount_policy(case_id="TC-DP-007")
        payload = dp.payload(user_id="u_dp_007", user_level="vip", scene="checkout", stock=5, request_id="req_dp_007")
        eval_resp = dp.evaluate(payload)
        assert eval_resp.status_code == 200
        query_resp = dp.query("req_dp_007")
        assert query_resp.status_code == 200
        body = query_resp.json()
        assert body["found"] is True
        assert body["request_id"] == "req_dp_007"
        assert body["decision"]["reason_code"] == "VIP_CHECKOUT"
        assert body["decision"]["request_id"] == "req_dp_007"

    def test_tc_dp_008(self, setup_discount_policy):
        """TC-DP-008：删除决策后查询返回不存在"""
        __tc_meta__ = {
            "tc_id": "TC-DP-008",
            "module": "discount_policy",
            "category": "business",
            "source": "test_workspace/suites/discount_system/discount_policy_smoke/business.md",
            "title": "删除决策后查询返回不存在",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 接口调用：先 POST /api/v1/discount/policy，再 DELETE /api/v1/discount/decisions/req_dp_008，最后查询同一 request_id
        # SETUP: 请求覆盖：{"user_id": "u_dp_008", "user_level": "normal", "scene": "campaign", "stock": 5, "request_id": "req_dp_008"}

        dp = setup_discount_policy
        dp = setup_discount_policy(case_id="TC-DP-008")
        payload = dp.payload(user_id="u_dp_008", user_level="normal", scene="campaign", stock=5, request_id="req_dp_008")
        eval_resp = dp.evaluate(payload)
        assert eval_resp.status_code == 200
        delete_resp = dp.delete("req_dp_008")
        assert delete_resp.status_code == 200
        deleted = delete_resp.json()
        assert deleted["deleted"] is True
        query_resp = dp.query("req_dp_008")
        assert query_resp.status_code == 404
        body = query_resp.json()
        assert body["found"] is False
        assert body["error"] == "DECISION_NOT_FOUND"


# TODO: setup_discount_policy fixture 需要手写实现（→ tests/fixtures/discount_policy.py）

__codegen_skipped__ = []
