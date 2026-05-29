# Auto-generated from test_workspace/suites/coupon_system/logging_smoke/business.md
# DO NOT EDIT — regenerate with: aitest codegen --suite-file test_workspace/suites/coupon_system/logging_smoke/suite.yaml
import pytest
from test_workspace.targets.coupon_system.helpers import http as http_helper
from test_workspace.targets.coupon_system.helpers import grpc_ops
from test_workspace.targets.coupon_system.fixtures.common import http_base_url, grpc_target, ab_base_url, redis_url, redis_tracker
import re
from test_workspace.targets.coupon_system.fixtures.logging import setup_logging


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
    "items": [{"item_id": "COUPON_LOG_001", "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 7}, {"item_id": "COUPON_LOG_002", "coupon_type": "fixed", "value": 5000, "min_spend": 20000, "expire_days": 7}],
}


def _req(**overrides) -> dict:
    body = {**BASE_REQUEST}
    body.update(overrides)
    return body


class TestLoggingBusiness:
    """logging 业务测试用例"""

    # ── 一、日志字段完整性 ──

    def test_tc_log_001(self, setup_logging):
        """TC-LOG-001：HTTP 内部打分请求记录 route=1"""
        __tc_meta__ = {
            "tc_id": "TC-LOG-001",
            "module": "logging",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/logging_smoke/business.md",
            "title": "HTTP 内部打分请求记录 route=1",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_log_http_internal"、external=0、reqId="req-log-001"

        case = setup_logging(case_id="TC-LOG-001")
        case.start_with_info_logging()
        resp = case.request("u_log_http_internal", "req-log-001", external=0)
        logs = case.stop_and_logs()
        assert resp["code"] == 0
        assert "recommend request: reqId=req-log-001" in logs
        assert "user_id=u_log_http_internal" in logs
        assert "item_ids=COUPON_LOG_001,COUPON_LOG_002" in logs
        assert "route=1" in logs
        assert "scene_id=1001" in logs

    def test_tc_log_002(self, setup_logging):
        """TC-LOG-002：gRPC 内部打分请求记录 route=1"""
        __tc_meta__ = {
            "tc_id": "TC-LOG-002",
            "module": "logging",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/logging_smoke/business.md",
            "title": "gRPC 内部打分请求记录 route=1",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 请求覆盖：gRPC 请求 user_id="u_log_grpc_internal"、external=0、req_id="req-log-002"

        case = setup_logging(case_id="TC-LOG-002")
        case.start_with_info_logging()
        resp = case.grpc_request("u_log_grpc_internal", "req-log-002", external=0)
        logs = case.stop_and_logs()
        assert resp["code"] == 0
        assert "recommend request: reqId=req-log-002" in logs
        assert "user_id=u_log_grpc_internal" in logs
        assert "route=1" in logs
        assert "scene_id=1001" in logs

    def test_tc_log_003(self, setup_logging):
        """TC-LOG-003：HTTP 外部打分请求记录 route=2"""
        __tc_meta__ = {
            "tc_id": "TC-LOG-003",
            "module": "logging",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/logging_smoke/business.md",
            "title": "HTTP 外部打分请求记录 route=2",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_log_http_external"、external=1、reqId="req-log-003"

        case = setup_logging(case_id="TC-LOG-003")
        case.start_with_info_logging()
        resp = case.request("u_log_http_external", "req-log-003", external=1)
        logs = case.stop_and_logs()
        assert resp["code"] == 0
        assert "recommend request: reqId=req-log-003" in logs
        assert "user_id=u_log_http_external" in logs
        assert "route=2" in logs
        assert "scene_id=1001" in logs

    def test_tc_log_004(self, setup_logging):
        """TC-LOG-004：gRPC 外部打分请求记录 route=2"""
        __tc_meta__ = {
            "tc_id": "TC-LOG-004",
            "module": "logging",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/logging_smoke/business.md",
            "title": "gRPC 外部打分请求记录 route=2",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 协议：gRPC
        # SETUP: 请求覆盖：gRPC 请求 user_id="u_log_grpc_external"、external=1、req_id="req-log-004"

        case = setup_logging(case_id="TC-LOG-004")
        case.start_with_info_logging()
        resp = case.grpc_request("u_log_grpc_external", "req-log-004", external=1)
        logs = case.stop_and_logs()
        assert resp["code"] == 0
        assert "recommend request: reqId=req-log-004" in logs
        assert "user_id=u_log_grpc_external" in logs
        assert "route=2" in logs
        assert "scene_id=1001" in logs

    # ── 二、reqId ──

    def test_tc_log_005(self, setup_logging):
        """TC-LOG-005：reqId 为空时日志记录自动生成 UUID"""
        __tc_meta__ = {
            "tc_id": "TC-LOG-005",
            "module": "logging",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/logging_smoke/business.md",
            "title": "reqId 为空时日志记录自动生成 UUID",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_log_auto_reqid"、external=0、reqId=""

        case = setup_logging(case_id="TC-LOG-005")
        case.start_with_info_logging()
        resp = case.request("u_log_auto_reqid", "", external=0)
        logs = case.stop_and_logs()
        assert resp["code"] == 0
        assert re.search(r"recommend request: reqId=[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", logs)

    def test_tc_log_006(self, setup_logging):
        """TC-LOG-006：兜底场景也记录 scene_id"""
        __tc_meta__ = {
            "tc_id": "TC-LOG-006",
            "module": "logging",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/logging_smoke/business.md",
            "title": "兜底场景也记录 scene_id",
            "priority": "P1",
            "markers": [],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_log_fallback"、policy_id="policy_fallback_001"、external=0、reqId="req-log-006"

        case = setup_logging(case_id="TC-LOG-006")
        case.start_with_info_logging()
        resp = case.request("u_log_fallback", "req-log-006", external=0, policy_id="policy_fallback_001")
        logs = case.stop_and_logs()
        assert resp["code"] == 0
        assert "recommend request: reqId=req-log-006" in logs
        assert "scene_id=3001" in logs

    # ── 三、route 隔离 ──

    @pytest.mark.manual
    def test_tc_log_007(self, setup_logging):
        """TC-LOG-007：route 字段不下发给内部打分服务"""
        __tc_meta__ = {
            "tc_id": "TC-LOG-007",
            "module": "logging",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/logging_smoke/business.md",
            "title": "route 字段不下发给内部打分服务",
            "priority": "P1",
            "markers": ["`[manual]`"],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_log_no_route_internal"、external=0、reqId="req-log-007"

        case = setup_logging(case_id="TC-LOG-007")
        case.start_with_info_logging()
        resp = case.request("u_log_no_route_internal", "req-log-007", external=0)
        case.stop_and_logs()
        assert resp["code"] == 0
        # MANUAL CHECK: 内部打分服务收到的请求字段中不存在 route

    @pytest.mark.manual
    def test_tc_log_008(self, setup_logging):
        """TC-LOG-008：route 字段不下发给外部打分服务"""
        __tc_meta__ = {
            "tc_id": "TC-LOG-008",
            "module": "logging",
            "category": "business",
            "source": "test_workspace/suites/coupon_system/logging_smoke/business.md",
            "title": "route 字段不下发给外部打分服务",
            "priority": "P1",
            "markers": ["`[manual]`"],
        }
        # SETUP: 协议：HTTP
        # SETUP: 请求覆盖：HTTP 请求 user_id="u_log_no_route_external"、external=1、reqId="req-log-008"

        case = setup_logging(case_id="TC-LOG-008")
        case.start_with_info_logging()
        resp = case.request("u_log_no_route_external", "req-log-008", external=1)
        case.stop_and_logs()
        assert resp["code"] == 0
        # MANUAL CHECK: 外部打分服务收到的 JSON body 中不存在 route


# TODO: setup_logging fixture 需要手写实现（→ tests/fixtures/logging.py）

__codegen_skipped__ = []
