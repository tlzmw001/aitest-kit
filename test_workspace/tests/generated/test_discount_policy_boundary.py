# Auto-generated from test_workspace/cases/discount_policy/boundary.md
# DO NOT EDIT — regenerate with: /test-codegen discount_policy
import pytest
from test_workspace.tests.helpers import http as http_helper


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


class TestDiscountPolicyBoundary:
    """discount_policy 边界测试用例"""

    # ── 一、字段边界 ──

    def test_tc_dp_009(self, setup_discount_policy):
        """TC-DP-009：item_price 为 0 仍可评估"""
        __tc_meta__ = {
            "tc_id": "TC-DP-009",
            "module": "discount_policy",
            "category": "boundary",
            "source": "test_workspace/cases/discount_policy/boundary.md",
            "title": "item_price 为 0 仍可评估",
            "priority": "P2",
            "markers": [],
        }
        # SETUP: 请求覆盖：{"user_id": "u_dp_009", "item_price": 0, "stock": 5, "request_id": "req_dp_009"}

        dp = setup_discount_policy(case_id="TC-DP-009")
        payload = dp.payload(user_id="u_dp_009", item_price=0, stock=5, request_id="req_dp_009")
        resp = dp.evaluate(payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["reason_code"] == "DEFAULT"
        assert body["request_id"] == "req_dp_009"

    def test_tc_dp_010(self, setup_discount_policy):
        """TC-DP-010：非法 user_level 触发校验错误且不存储"""
        __tc_meta__ = {
            "tc_id": "TC-DP-010",
            "module": "discount_policy",
            "category": "boundary",
            "source": "test_workspace/cases/discount_policy/boundary.md",
            "title": "非法 user_level 触发校验错误且不存储",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 请求覆盖：{"user_id": "u_dp_010", "user_level": "gold", "request_id": "req_dp_010"}

        dp = setup_discount_policy(case_id="TC-DP-010")
        payload = dp.payload(user_id="u_dp_010", user_level="gold", request_id="req_dp_010")
        resp = dp.evaluate(payload)
        assert resp.status_code >= 400
        query_resp = dp.query("req_dp_010")
        assert query_resp.status_code == 404
        body = query_resp.json()
        assert body["error"] == "DECISION_NOT_FOUND"

    def test_tc_dp_011(self, setup_discount_policy):
        """TC-DP-011：非法 scene 触发校验错误且不存储"""
        __tc_meta__ = {
            "tc_id": "TC-DP-011",
            "module": "discount_policy",
            "category": "boundary",
            "source": "test_workspace/cases/discount_policy/boundary.md",
            "title": "非法 scene 触发校验错误且不存储",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 请求覆盖：{"user_id": "u_dp_011", "scene": "unknown", "request_id": "req_dp_011"}

        dp = setup_discount_policy(case_id="TC-DP-011")
        payload = dp.payload(user_id="u_dp_011", scene="unknown", request_id="req_dp_011")
        resp = dp.evaluate(payload)
        assert resp.status_code >= 400
        query_resp = dp.query("req_dp_011")
        assert query_resp.status_code == 404
        body = query_resp.json()
        assert body["error"] == "DECISION_NOT_FOUND"

    def test_tc_dp_012(self, setup_discount_policy):
        """TC-DP-012：负数 item_price 触发校验错误且不存储"""
        __tc_meta__ = {
            "tc_id": "TC-DP-012",
            "module": "discount_policy",
            "category": "boundary",
            "source": "test_workspace/cases/discount_policy/boundary.md",
            "title": "负数 item_price 触发校验错误且不存储",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 请求覆盖：{"user_id": "u_dp_012", "item_price": -0.01, "request_id": "req_dp_012"}

        dp = setup_discount_policy(case_id="TC-DP-012")
        payload = dp.payload(user_id="u_dp_012", item_price=-0.01, request_id="req_dp_012")
        resp = dp.evaluate(payload)
        assert resp.status_code >= 400
        query_resp = dp.query("req_dp_012")
        assert query_resp.status_code == 404
        body = query_resp.json()
        assert body["error"] == "DECISION_NOT_FOUND"

    def test_tc_dp_013(self, setup_discount_policy):
        """TC-DP-013：负数 stock 触发校验错误且不存储"""
        __tc_meta__ = {
            "tc_id": "TC-DP-013",
            "module": "discount_policy",
            "category": "boundary",
            "source": "test_workspace/cases/discount_policy/boundary.md",
            "title": "负数 stock 触发校验错误且不存储",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 请求覆盖：{"user_id": "u_dp_013", "stock": -1, "request_id": "req_dp_013"}

        dp = setup_discount_policy(case_id="TC-DP-013")
        payload = dp.payload(user_id="u_dp_013", stock=-1, request_id="req_dp_013")
        resp = dp.evaluate(payload)
        assert resp.status_code >= 400
        query_resp = dp.query("req_dp_013")
        assert query_resp.status_code == 404
        body = query_resp.json()
        assert body["error"] == "DECISION_NOT_FOUND"

    def test_tc_dp_014(self, setup_discount_policy):
        """TC-DP-014：缺少必填字段触发校验错误且不存储"""
        __tc_meta__ = {
            "tc_id": "TC-DP-014",
            "module": "discount_policy",
            "category": "boundary",
            "source": "test_workspace/cases/discount_policy/boundary.md",
            "title": "缺少必填字段触发校验错误且不存储",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 请求体：删除 user_id，保留 request_id="req_dp_014"

        dp = setup_discount_policy(case_id="TC-DP-014")
        payload = dp.payload_without("user_id", request_id="req_dp_014")
        resp = dp.evaluate(payload)
        assert resp.status_code >= 400
        query_resp = dp.query("req_dp_014")
        assert query_resp.status_code == 404
        body = query_resp.json()
        assert body["error"] == "DECISION_NOT_FOUND"

    # ── 二、决策记录边界 ──

    def test_tc_dp_015(self, setup_discount_policy):
        """TC-DP-015：查询不存在决策返回 404"""
        __tc_meta__ = {
            "tc_id": "TC-DP-015",
            "module": "discount_policy",
            "category": "boundary",
            "source": "test_workspace/cases/discount_policy/boundary.md",
            "title": "查询不存在决策返回 404",
            "priority": "P1 / 异常",
            "markers": [],
        }
        # SETUP: 接口调用：GET /api/v1/discount/decisions/req_dp_missing_015

        dp = setup_discount_policy(case_id="TC-DP-015")
        resp = dp.query("req_dp_missing_015")
        assert resp.status_code == 404
        body = resp.json()
        assert body["found"] is False
        assert body["request_id"] == "req_dp_missing_015"
        assert body["error"] == "DECISION_NOT_FOUND"

    def test_tc_dp_016(self, setup_discount_policy):
        """TC-DP-016：删除不存在决策返回 deleted false"""
        __tc_meta__ = {
            "tc_id": "TC-DP-016",
            "module": "discount_policy",
            "category": "boundary",
            "source": "test_workspace/cases/discount_policy/boundary.md",
            "title": "删除不存在决策返回 deleted false",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 接口调用：DELETE /api/v1/discount/decisions/req_dp_missing_016

        dp = setup_discount_policy(case_id="TC-DP-016")
        resp = dp.delete("req_dp_missing_016")
        assert resp.status_code == 200
        body = resp.json()
        assert body["deleted"] is False
        assert body["request_id"] == "req_dp_missing_016"



__codegen_skipped__ = []
