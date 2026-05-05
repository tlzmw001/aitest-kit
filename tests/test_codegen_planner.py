"""Unit tests for planner strategy determination and Case IR construction.

Focuses on edge cases in strategy priority, protocol detection, fixture
selection, and diagnostic generation — areas not covered by the integration
tests in test_codegen_ir.py.
"""
from __future__ import annotations

from aitest_kit.codegen.ir import FileIR
from aitest_kit.codegen.parser import ParseResult, SharedConfig, TestCase
from aitest_kit.codegen.planner import build_file_ir
from aitest_kit.codegen.project_config import DEFAULT_PROJECT


def _parse_result(
    cases: list[TestCase],
    base_request_http: dict | None = None,
    common_assertions: list[str] | None = None,
    variables: dict[str, str] | None = None,
) -> ParseResult:
    return ParseResult(
        module="demo",
        source_file="test_workspace/cases/demo/business.md",
        shared_config=SharedConfig(
            base_request_http=base_request_http or {"user_id": "", "reqId": ""},
            common_assertions=common_assertions or [],
            variables=variables or {},
        ),
        cases=cases,
    )


def _case(file_ir: FileIR, case_id: str):
    for case_ir in file_ir.cases:
        if case_ir.case_id == case_id:
            return case_ir
    raise AssertionError(f"{case_id} not found in IR")


# ---------------------------------------------------------------------------
# Strategy priority tests
# ---------------------------------------------------------------------------


class TestStrategyPriority:
    """Verify strategy priority: skipped > custom_case_body > structured_case_flow > manual > default_grpc > default_http."""

    def test_skipped_overrides_everything(self, tmp_path):
        profile_path = tmp_path / "codegen_profile_demo.md"
        profile_path.write_text(
            """```yaml
case_bodies:
  TC-DEMO-001: |
    resp = case.http()
```
""",
            encoding="utf-8",
        )
        tc = TestCase(
            id="TC-DEMO-001",
            title="同时有 case_body 和 skip",
            priority="P1",
            markers=["[!可行性存疑: 服务未部署]"],
            scenario_vars={"协议": "gRPC"},
            section="优先级",
        )
        file_ir = build_file_ir(
            _parse_result([tc]),
            "business",
            profile_path=profile_path,
            project=DEFAULT_PROJECT,
        )
        case_ir = _case(file_ir, "TC-DEMO-001")
        assert case_ir.strategy == "skipped"
        assert case_ir.skip_reason == "[!可行性存疑: 服务未部署]"

    def test_case_body_overrides_case_flow(self, tmp_path):
        profile_path = tmp_path / "codegen_profile_demo.md"
        profile_path.write_text(
            """```yaml
case_bodies:
  TC-DEMO-001: |
    resp = case.http()
```
""",
            encoding="utf-8",
        )
        tc = TestCase(
            id="TC-DEMO-001",
            title="有 case_body 无 case_flow",
            priority="P1",
            markers=["[manual]"],
            scenario_vars={"协议": "gRPC"},
            section="优先级",
        )
        file_ir = build_file_ir(
            _parse_result([tc]),
            "business",
            profile_path=profile_path,
            project=DEFAULT_PROJECT,
        )
        case_ir = _case(file_ir, "TC-DEMO-001")
        assert case_ir.strategy == "custom_case_body"

    def test_case_flow_overrides_manual_and_grpc(self, tmp_path):
        profile_path = tmp_path / "codegen_profile_demo.md"
        profile_path.write_text(
            """```yaml
case_flows:
  TC-DEMO-001:
    fixture: setup_demo
    steps:
      - call: setup_demo
        save_as: case
      - assert: "assert True"
```
""",
            encoding="utf-8",
        )
        tc = TestCase(
            id="TC-DEMO-001",
            title="有 case_flow 和 manual",
            priority="P1",
            markers=["[manual]"],
            scenario_vars={"协议": "gRPC"},
            section="优先级",
        )
        file_ir = build_file_ir(
            _parse_result([tc]),
            "business",
            profile_path=profile_path,
            project=DEFAULT_PROJECT,
        )
        case_ir = _case(file_ir, "TC-DEMO-001")
        assert case_ir.strategy == "structured_case_flow"

    def test_manual_overrides_grpc(self, tmp_path):
        tc = TestCase(
            id="TC-DEMO-001",
            title="manual 且有 gRPC",
            priority="P1",
            markers=["[manual]"],
            scenario_vars={"协议": "gRPC"},
            section="优先级",
        )
        file_ir = build_file_ir(
            _parse_result([tc]),
            "business",
            project=DEFAULT_PROJECT,
        )
        case_ir = _case(file_ir, "TC-DEMO-001")
        assert case_ir.strategy == "manual"

    def test_grpc_overrides_http(self, tmp_path):
        tc = TestCase(
            id="TC-DEMO-001",
            title="有 gRPC 场景变量",
            priority="P1",
            scenario_vars={"协议": "gRPC"},
            section="优先级",
        )
        file_ir = build_file_ir(
            _parse_result([tc]),
            "business",
            project=DEFAULT_PROJECT,
        )
        case_ir = _case(file_ir, "TC-DEMO-001")
        assert case_ir.strategy == "default_grpc"
        assert case_ir.protocol == "grpc"

    def test_default_http_is_lowest_priority(self):
        tc = TestCase(
            id="TC-DEMO-001",
            title="无特殊标记",
            priority="P1",
            section="默认",
        )
        file_ir = build_file_ir(
            _parse_result([tc]),
            "business",
            project=DEFAULT_PROJECT,
        )
        case_ir = _case(file_ir, "TC-DEMO-001")
        assert case_ir.strategy == "default_http"
        assert case_ir.protocol == "http"


# ---------------------------------------------------------------------------
# Protocol detection
# ---------------------------------------------------------------------------


class TestProtocolDetection:

    def test_custom_case_body_protocol_is_custom(self, tmp_path):
        profile_path = tmp_path / "codegen_profile_demo.md"
        profile_path.write_text(
            """```yaml
case_bodies:
  TC-DEMO-001: |
    resp = custom_call()
```
""",
            encoding="utf-8",
        )
        tc = TestCase(id="TC-DEMO-001", title="custom", priority="P1", section="协议")
        file_ir = build_file_ir(
            _parse_result([tc]),
            "business",
            profile_path=profile_path,
            project=DEFAULT_PROJECT,
        )
        assert _case(file_ir, "TC-DEMO-001").protocol == "custom"

    def test_structured_case_flow_protocol_is_flow(self, tmp_path):
        profile_path = tmp_path / "codegen_profile_demo.md"
        profile_path.write_text(
            """```yaml
case_flows:
  TC-DEMO-001:
    fixture: setup_demo
    steps:
      - call: setup_demo
        save_as: case
      - assert: "assert True"
```
""",
            encoding="utf-8",
        )
        tc = TestCase(id="TC-DEMO-001", title="flow", priority="P1", section="协议")
        file_ir = build_file_ir(
            _parse_result([tc]),
            "business",
            profile_path=profile_path,
            project=DEFAULT_PROJECT,
        )
        assert _case(file_ir, "TC-DEMO-001").protocol == "flow"

    def test_grpc_detected_from_scenario_var_value(self):
        tc = TestCase(
            id="TC-DEMO-001",
            title="gRPC",
            priority="P1",
            scenario_vars={"传输协议": "使用 gRPC 接口"},
            section="协议",
        )
        file_ir = build_file_ir(_parse_result([tc]), "business", project=DEFAULT_PROJECT)
        case_ir = _case(file_ir, "TC-DEMO-001")
        assert case_ir.protocol == "grpc"
        assert case_ir.source_trace["protocol"].source == "scenario_vars.传输协议"


# ---------------------------------------------------------------------------
# Fixture selection
# ---------------------------------------------------------------------------


class TestFixtureSelection:

    def test_default_http_fixtures(self):
        tc = TestCase(id="TC-DEMO-001", title="http", priority="P1", section="fixture")
        file_ir = build_file_ir(_parse_result([tc]), "business", project=DEFAULT_PROJECT)
        assert _case(file_ir, "TC-DEMO-001").fixtures == ["http_base_url", "setup_demo"]

    def test_default_grpc_fixtures(self):
        tc = TestCase(
            id="TC-DEMO-001",
            title="grpc",
            priority="P1",
            scenario_vars={"协议": "gRPC"},
            section="fixture",
        )
        file_ir = build_file_ir(_parse_result([tc]), "business", project=DEFAULT_PROJECT)
        assert _case(file_ir, "TC-DEMO-001").fixtures == ["grpc_target", "setup_demo"]

    def test_case_flow_uses_flow_fixture(self, tmp_path):
        profile_path = tmp_path / "codegen_profile_demo.md"
        profile_path.write_text(
            """```yaml
case_flows:
  TC-DEMO-001:
    fixture: custom_fixture
    steps:
      - call: custom_fixture
        save_as: obj
      - assert: "assert True"
```
""",
            encoding="utf-8",
        )
        tc = TestCase(id="TC-DEMO-001", title="flow", priority="P1", section="fixture")
        file_ir = build_file_ir(
            _parse_result([tc]),
            "business",
            profile_path=profile_path,
            project=DEFAULT_PROJECT,
        )
        assert _case(file_ir, "TC-DEMO-001").fixtures == ["custom_fixture"]

    def test_case_body_uses_case_fixtures_override(self, tmp_path):
        profile_path = tmp_path / "codegen_profile_demo.md"
        profile_path.write_text(
            """```yaml
case_bodies:
  TC-DEMO-001: |
    resp = special()
case_fixtures:
  TC-DEMO-001:
    - tmp_path
    - redis_url
```
""",
            encoding="utf-8",
        )
        tc = TestCase(id="TC-DEMO-001", title="custom fixture", priority="P1", section="fixture")
        file_ir = build_file_ir(
            _parse_result([tc]),
            "business",
            profile_path=profile_path,
            project=DEFAULT_PROJECT,
        )
        assert _case(file_ir, "TC-DEMO-001").fixtures == ["tmp_path", "redis_url"]

    def test_skipped_case_has_no_fixtures(self):
        tc = TestCase(
            id="TC-DEMO-001",
            title="skip",
            priority="P1",
            markers=["[!可行性存疑: 无法测试]"],
            section="fixture",
        )
        file_ir = build_file_ir(_parse_result([tc]), "business", project=DEFAULT_PROJECT)
        assert _case(file_ir, "TC-DEMO-001").fixtures == []


# ---------------------------------------------------------------------------
# Source trace
# ---------------------------------------------------------------------------


class TestSourceTrace:

    def test_default_http_strategy_trace(self):
        tc = TestCase(id="TC-DEMO-001", title="http", priority="P1", section="trace")
        file_ir = build_file_ir(_parse_result([tc]), "business", project=DEFAULT_PROJECT)
        case_ir = _case(file_ir, "TC-DEMO-001")
        assert case_ir.source_trace["strategy"].value == "default_http"
        assert case_ir.source_trace["strategy"].source == "default"

    def test_case_body_strategy_trace(self, tmp_path):
        profile_path = tmp_path / "codegen_profile_demo.md"
        profile_path.write_text(
            """```yaml
case_bodies:
  TC-DEMO-001: |
    pass
```
""",
            encoding="utf-8",
        )
        tc = TestCase(id="TC-DEMO-001", title="body", priority="P1", section="trace")
        file_ir = build_file_ir(
            _parse_result([tc]),
            "business",
            profile_path=profile_path,
            project=DEFAULT_PROJECT,
        )
        case_ir = _case(file_ir, "TC-DEMO-001")
        assert case_ir.source_trace["strategy"].value == "custom_case_body"
        assert "profile.case_bodies" in case_ir.source_trace["strategy"].source

    def test_request_overrides_trace(self, tmp_path):
        profile_path = tmp_path / "codegen_profile_demo.md"
        profile_path.write_text(
            """```yaml
request_overrides:
  TC-DEMO-001:
    external: 1
    score_threshold: 0.8
```
""",
            encoding="utf-8",
        )
        tc = TestCase(id="TC-DEMO-001", title="overrides", priority="P1", section="trace")
        file_ir = build_file_ir(
            _parse_result([tc]),
            "business",
            profile_path=profile_path,
            project=DEFAULT_PROJECT,
        )
        case_ir = _case(file_ir, "TC-DEMO-001")
        assert "request_overrides" in case_ir.source_trace
        assert case_ir.request.overrides == {"external": 1, "score_threshold": 0.8}


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


class TestDiagnostics:

    def test_parser_errors_propagate_to_file_ir(self):
        parse_result = ParseResult(
            module="demo",
            source_file="test_workspace/cases/demo/business.md",
            shared_config=SharedConfig(),
            cases=[],
            errors=["E001: invalid JSON in request body"],
        )
        file_ir = build_file_ir(parse_result, "business", project=DEFAULT_PROJECT)
        assert any(d.code == "E001" for d in file_ir.diagnostics)

    def test_no_base_request_without_coverage_produces_no_file_diagnostics(self):
        tc = TestCase(id="TC-DEMO-001", title="no request", priority="P1", section="diag")
        parse_result = ParseResult(
            module="demo",
            source_file="test_workspace/cases/demo/business.md",
            shared_config=SharedConfig(base_request_http=None),
            cases=[tc],
        )
        file_ir = build_file_ir(parse_result, "business", project=DEFAULT_PROJECT)
        case_ir = _case(file_ir, "TC-DEMO-001")
        assert any(d.code == "E202" for d in case_ir.diagnostics)

    def test_case_flow_covered_case_no_e202(self, tmp_path):
        profile_path = tmp_path / "codegen_profile_demo.md"
        profile_path.write_text(
            """```yaml
case_flows:
  TC-DEMO-001:
    fixture: setup_demo
    steps:
      - call: setup_demo
        save_as: case
      - assert: "assert True"
```
""",
            encoding="utf-8",
        )
        tc = TestCase(id="TC-DEMO-001", title="flow", priority="P1", section="diag")
        parse_result = ParseResult(
            module="demo",
            source_file="test_workspace/cases/demo/business.md",
            shared_config=SharedConfig(base_request_http=None),
            cases=[tc],
        )
        file_ir = build_file_ir(
            parse_result, "business", profile_path=profile_path, project=DEFAULT_PROJECT
        )
        case_ir = _case(file_ir, "TC-DEMO-001")
        assert not any(d.code == "E202" for d in case_ir.diagnostics)


# ---------------------------------------------------------------------------
# Request IR
# ---------------------------------------------------------------------------


class TestRequestIR:

    def test_default_user_id_and_req_id_format(self):
        tc = TestCase(id="TC-DEMO-003", title="request", priority="P1", section="req")
        file_ir = build_file_ir(_parse_result([tc]), "business", project=DEFAULT_PROJECT)
        case_ir = _case(file_ir, "TC-DEMO-003")
        assert case_ir.request.user_id == "u_demo_003"
        assert case_ir.request.req_id == "req_demo_003"

    def test_request_overrides_merge(self, tmp_path):
        profile_path = tmp_path / "codegen_profile_demo.md"
        profile_path.write_text(
            """```yaml
request_overrides:
  TC-DEMO-001:
    user_id: custom_user
    external: 1
```
""",
            encoding="utf-8",
        )
        tc = TestCase(id="TC-DEMO-001", title="override", priority="P1", section="req")
        file_ir = build_file_ir(
            _parse_result([tc]),
            "business",
            profile_path=profile_path,
            project=DEFAULT_PROJECT,
        )
        case_ir = _case(file_ir, "TC-DEMO-001")
        assert case_ir.request.user_id == "custom_user"
        assert case_ir.request.overrides == {"external": 1}

    def test_no_request_for_case_body(self, tmp_path):
        profile_path = tmp_path / "codegen_profile_demo.md"
        profile_path.write_text(
            """```yaml
case_bodies:
  TC-DEMO-001: |
    pass
```
""",
            encoding="utf-8",
        )
        tc = TestCase(id="TC-DEMO-001", title="body", priority="P1", section="req")
        file_ir = build_file_ir(
            _parse_result([tc]),
            "business",
            profile_path=profile_path,
            project=DEFAULT_PROJECT,
        )
        assert _case(file_ir, "TC-DEMO-001").request is None

    def test_no_request_for_case_flow(self, tmp_path):
        profile_path = tmp_path / "codegen_profile_demo.md"
        profile_path.write_text(
            """```yaml
case_flows:
  TC-DEMO-001:
    fixture: setup_demo
    steps:
      - call: setup_demo
        save_as: case
      - assert: "assert True"
```
""",
            encoding="utf-8",
        )
        tc = TestCase(id="TC-DEMO-001", title="flow", priority="P1", section="req")
        file_ir = build_file_ir(
            _parse_result([tc]),
            "business",
            profile_path=profile_path,
            project=DEFAULT_PROJECT,
        )
        assert _case(file_ir, "TC-DEMO-001").request is None
