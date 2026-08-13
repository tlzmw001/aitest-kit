# Auto-generated from test_workspace/suites/discount_system/discount_policy_smoke/boundary.md
# DO NOT EDIT — regenerate with: aitest codegen --suite-file test_workspace/suites/discount_system/discount_policy_smoke/suite.yaml
import pytest
from aitest_kit.helpers import http as http_helper
from aitest_kit.helpers.request_binding import build_request
from aitest_kit.runtime_context import reset_case_context, set_case_context
pytest_plugins = ["test_workspace.targets.discount_system.modules.discount_policy.fixture"]


BASE_REQUEST = {
    "user_id": None,
    "user_level": "normal",
    "item_id": "item_dp_default",
    "item_price": 120.5,
    "scene": "checkout",
    "stock": 5,
    "request_id": "req_dp_default",
}


def _req(*, auto_fields=None, overrides=None, patches=None) -> dict:
    return build_request(
        BASE_REQUEST,
        auto_fields=auto_fields or {},
        overrides=overrides or {},
        patches=patches or [],
    )


class TestDiscountPolicyBoundary:
    """discount_policy 边界测试用例"""

    # ── 一、字段边界 ──

    def test_tc_dp_009(self, setup_discount_policy):
        """TC-DP-009：item_price 为 0 仍可评估"""
        __tc_meta__ = {
            "tc_id": "TC-DP-009",
            "module": "discount_policy",
            "category": "boundary",
            "source": "test_workspace/suites/discount_system/discount_policy_smoke/boundary.md",
            "title": "item_price 为 0 仍可评估",
            "priority": "P2",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 请求覆盖：{"user_id": "u_dp_009", "item_price": 0, "stock": 5, "request_id": "req_dp_009"}

            harness = setup_discount_policy
            payload = harness.payload(user_id="u_dp_009", item_price=0, stock=5, request_id="req_dp_009")
            resp = harness.evaluate(payload)
            assert resp.status_code == 200
            body = resp.json()
            assert body["code"] == 0
            assert body["reason_code"] == "DEFAULT"
            assert body["request_id"] == "req_dp_009"
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_dp_010(self, setup_discount_policy):
        """TC-DP-010：非法 user_level 触发校验错误且不存储"""
        __tc_meta__ = {
            "tc_id": "TC-DP-010",
            "module": "discount_policy",
            "category": "boundary",
            "source": "test_workspace/suites/discount_system/discount_policy_smoke/boundary.md",
            "title": "非法 user_level 触发校验错误且不存储",
            "priority": "P1 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 请求覆盖：{"user_id": "u_dp_010", "user_level": "gold", "request_id": "req_dp_010"}

            harness = setup_discount_policy
            payload = harness.payload(user_id="u_dp_010", user_level="gold", request_id="req_dp_010")
            resp = harness.evaluate(payload)
            assert resp.status_code >= 400
            query_resp = harness.query("req_dp_010")
            assert query_resp.status_code == 404
            body = query_resp.json()
            assert body["error"] == "DECISION_NOT_FOUND"
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_dp_011(self, setup_discount_policy):
        """TC-DP-011：非法 scene 触发校验错误且不存储"""
        __tc_meta__ = {
            "tc_id": "TC-DP-011",
            "module": "discount_policy",
            "category": "boundary",
            "source": "test_workspace/suites/discount_system/discount_policy_smoke/boundary.md",
            "title": "非法 scene 触发校验错误且不存储",
            "priority": "P1 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 请求覆盖：{"user_id": "u_dp_011", "scene": "unknown", "request_id": "req_dp_011"}

            harness = setup_discount_policy
            payload = harness.payload(user_id="u_dp_011", scene="unknown", request_id="req_dp_011")
            resp = harness.evaluate(payload)
            assert resp.status_code >= 400
            query_resp = harness.query("req_dp_011")
            assert query_resp.status_code == 404
            body = query_resp.json()
            assert body["error"] == "DECISION_NOT_FOUND"
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_dp_012(self, setup_discount_policy):
        """TC-DP-012：负数 item_price 触发校验错误且不存储"""
        __tc_meta__ = {
            "tc_id": "TC-DP-012",
            "module": "discount_policy",
            "category": "boundary",
            "source": "test_workspace/suites/discount_system/discount_policy_smoke/boundary.md",
            "title": "负数 item_price 触发校验错误且不存储",
            "priority": "P1 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 请求覆盖：{"user_id": "u_dp_012", "item_price": -0.01, "request_id": "req_dp_012"}

            harness = setup_discount_policy
            payload = harness.payload(user_id="u_dp_012", item_price=-0.01, request_id="req_dp_012")
            resp = harness.evaluate(payload)
            assert resp.status_code >= 400
            query_resp = harness.query("req_dp_012")
            assert query_resp.status_code == 404
            body = query_resp.json()
            assert body["error"] == "DECISION_NOT_FOUND"
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_dp_013(self, setup_discount_policy):
        """TC-DP-013：负数 stock 触发校验错误且不存储"""
        __tc_meta__ = {
            "tc_id": "TC-DP-013",
            "module": "discount_policy",
            "category": "boundary",
            "source": "test_workspace/suites/discount_system/discount_policy_smoke/boundary.md",
            "title": "负数 stock 触发校验错误且不存储",
            "priority": "P1 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 请求覆盖：{"user_id": "u_dp_013", "stock": -1, "request_id": "req_dp_013"}

            harness = setup_discount_policy
            payload = harness.payload(user_id="u_dp_013", stock=-1, request_id="req_dp_013")
            resp = harness.evaluate(payload)
            assert resp.status_code >= 400
            query_resp = harness.query("req_dp_013")
            assert query_resp.status_code == 404
            body = query_resp.json()
            assert body["error"] == "DECISION_NOT_FOUND"
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_dp_014(self, setup_discount_policy):
        """TC-DP-014：缺少必填字段触发校验错误且不存储"""
        __tc_meta__ = {
            "tc_id": "TC-DP-014",
            "module": "discount_policy",
            "category": "boundary",
            "source": "test_workspace/suites/discount_system/discount_policy_smoke/boundary.md",
            "title": "缺少必填字段触发校验错误且不存储",
            "priority": "P1 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 请求体：删除 user_id，保留 request_id="req_dp_014"

            harness = setup_discount_policy
            payload = harness.payload_without("user_id", request_id="req_dp_014")
            resp = harness.evaluate(payload)
            assert resp.status_code >= 400
            query_resp = harness.query("req_dp_014")
            assert query_resp.status_code == 404
            body = query_resp.json()
            assert body["error"] == "DECISION_NOT_FOUND"
        finally:
            reset_case_context(__aitest_ctx_token)

    # ── 二、决策记录边界 ──

    def test_tc_dp_015(self, setup_discount_policy):
        """TC-DP-015：查询不存在决策返回 404"""
        __tc_meta__ = {
            "tc_id": "TC-DP-015",
            "module": "discount_policy",
            "category": "boundary",
            "source": "test_workspace/suites/discount_system/discount_policy_smoke/boundary.md",
            "title": "查询不存在决策返回 404",
            "priority": "P1 / 异常",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 接口调用：GET /api/v1/discount/decisions/req_dp_missing_015

            harness = setup_discount_policy
            resp = harness.query("req_dp_missing_015")
            assert resp.status_code == 404
            body = resp.json()
            assert body["found"] is False
            assert body["request_id"] == "req_dp_missing_015"
            assert body["error"] == "DECISION_NOT_FOUND"
        finally:
            reset_case_context(__aitest_ctx_token)

    def test_tc_dp_016(self, setup_discount_policy):
        """TC-DP-016：删除不存在决策返回 deleted false"""
        __tc_meta__ = {
            "tc_id": "TC-DP-016",
            "module": "discount_policy",
            "category": "boundary",
            "source": "test_workspace/suites/discount_system/discount_policy_smoke/boundary.md",
            "title": "删除不存在决策返回 deleted false",
            "priority": "P1",
            "markers": [],
        }
        __aitest_ctx_token = set_case_context(__tc_meta__["tc_id"], __tc_meta__)
        try:
            # SETUP: 接口调用：DELETE /api/v1/discount/decisions/req_dp_missing_016

            harness = setup_discount_policy
            resp = harness.delete("req_dp_missing_016")
            assert resp.status_code == 200
            body = resp.json()
            assert body["deleted"] is False
            assert body["request_id"] == "req_dp_missing_016"
        finally:
            reset_case_context(__aitest_ctx_token)



__codegen_skipped__ = []
