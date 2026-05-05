"""Protocol detection regression tests for Case IR planning."""
from __future__ import annotations

from aitest_kit.codegen.parser import ParseResult, SharedConfig, TestCase
from aitest_kit.codegen.planner import build_file_ir
from aitest_kit.codegen.project_config import DEFAULT_PROJECT


def _single_case_ir(tc: TestCase):
    result = ParseResult(
        module="demo",
        source_file="test_workspace/cases/demo/business.md",
        shared_config=SharedConfig(base_request_http={"user_id": "", "reqId": ""}),
        cases=[tc],
    )
    return build_file_ir(result, "business", project=DEFAULT_PROJECT).cases[0]


def test_environment_grpc_dependency_does_not_force_grpc_protocol():
    tc = TestCase(
        id="TC-DEMO-001",
        title="HTTP request with internal gRPC dependency",
        priority="P1",
        scenario_vars={
            "协议": "HTTP",
            "环境覆盖": "启动 Redis、AB 服务、内部 gRPC mock 打分服务和主服务",
        },
        section="协议检测",
    )

    case_ir = _single_case_ir(tc)

    assert case_ir.strategy == "default_http"
    assert case_ir.protocol == "http"
    assert case_ir.source_trace["protocol"].source == "default"


def test_protocol_field_can_still_select_grpc():
    tc = TestCase(
        id="TC-DEMO-002",
        title="gRPC request",
        priority="P1",
        scenario_vars={"协议": "gRPC"},
        section="协议检测",
    )

    case_ir = _single_case_ir(tc)

    assert case_ir.strategy == "default_grpc"
    assert case_ir.protocol == "grpc"
    assert case_ir.source_trace["protocol"].source == "scenario_vars.协议"
