import json
from pathlib import Path

from click.testing import CliRunner

from aitest_kit.codegen.cli import codegen
from aitest_kit.codegen.emitter import emit_file, emit_module
from aitest_kit.codegen.ir import ir_to_dict
from aitest_kit.codegen.parser import ParseResult, SharedConfig, TestCase as ParsedTestCase, parse_case_file
from aitest_kit.codegen.planner import build_file_ir
from aitest_kit.codegen.project_config import load_project_config
from aitest_kit.codegen.profile import (
    load_profile_case_flows,
    validate_case_flows,
    validate_profile_strategy_conflicts,
)


def _profile(module: str) -> Path:
    return Path("test_workspace/tests/fixtures") / f"codegen_profile_{module}.md"


def _case(file_ir, case_id: str):
    for case_ir in file_ir.cases:
        if case_ir.case_id == case_id:
            return case_ir
    raise AssertionError(f"{case_id} not found")


def test_ir_marks_default_grpc_strategy_with_source_trace():
    parse_result = parse_case_file("test_workspace/cases/calibration/boundary.md")
    file_ir = build_file_ir(
        parse_result,
        "boundary",
        profile_path=_profile("calibration"),
        project=load_project_config(),
    )

    case_ir = _case(file_ir, "TC-CAL-025")

    assert case_ir.strategy == "default_grpc"
    assert case_ir.protocol == "grpc"
    assert case_ir.fixtures == ["grpc_target", "setup_calibration"]
    assert case_ir.source_trace["protocol"].source == "scenario_vars.协议"
    assert case_ir.call.helper == "grpc_ops.recommend"


def test_ir_marks_profile_case_body_without_default_request_plan():
    parse_result = parse_case_file("test_workspace/cases/ab_service/business.md")
    file_ir = build_file_ir(
        parse_result,
        "business",
        profile_path=_profile("ab_service"),
        project=load_project_config(),
    )

    case_ir = _case(file_ir, "TC-ABS-012")

    assert case_ir.strategy == "custom_case_body"
    assert case_ir.protocol == "custom"
    assert case_ir.request is None
    assert case_ir.call is None
    assert case_ir.fixtures == ["tmp_path"]
    assert case_ir.custom_body is not None
    assert any("build_isolated_client" in line for line in case_ir.custom_body.lines)


def test_ir_marks_profile_case_flow_without_default_request_plan():
    parse_result = parse_case_file("test_workspace/cases/ab_service/business.md")
    file_ir = build_file_ir(
        parse_result,
        "business",
        profile_path=_profile("ab_service"),
        project=load_project_config(),
    )

    case_ir = _case(file_ir, "TC-ABS-001")

    assert case_ir.strategy == "structured_case_flow"
    assert case_ir.protocol == "flow"
    assert case_ir.request is None
    assert case_ir.call is None
    assert case_ir.fixtures == ["setup_ab_service"]
    assert case_ir.case_flow is not None
    assert case_ir.case_flow.steps[1].call == "ab.get"


def test_ir_serializes_to_plain_json_data():
    parse_result = parse_case_file("test_workspace/cases/calibration/boundary.md")
    file_ir = build_file_ir(
        parse_result,
        "boundary",
        profile_path=_profile("calibration"),
        project=load_project_config(),
    )

    payload = ir_to_dict(_case(file_ir, "TC-CAL-025"))

    assert payload["case_id"] == "TC-CAL-025"
    assert payload["strategy"] == "default_grpc"
    json.dumps(payload, ensure_ascii=False)


def test_codegen_explain_prints_single_case_ir():
    result = CliRunner().invoke(codegen, ["calibration", "--explain", "TC-CAL-025"])

    assert result.exit_code == 0
    assert "case_id: TC-CAL-025" in result.output
    assert "strategy: default_grpc" in result.output
    assert "protocol: grpc" in result.output


def test_codegen_dump_ir_prints_json_payload():
    result = CliRunner().invoke(codegen, ["calibration", "--dump-ir"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["modules"][0]["module"] == "calibration"
    assert payload["modules"][0]["files"][0]["cases"]


def test_emitter_renders_existing_generated_output_from_ir(tmp_path):
    results = emit_module("calibration", output_dir=tmp_path)

    assert not any(result.diagnostics for result in results)
    generated = Path("test_workspace/tests/generated/test_calibration_boundary.py")
    emitted = tmp_path / "test_calibration_boundary.py"
    assert emitted.read_text(encoding="utf-8") == generated.read_text(encoding="utf-8")


def test_emitter_reports_unparsed_common_assertions(tmp_path):
    parse_result = ParseResult(
        module="demo",
        source_file="test_workspace/cases/demo/business.md",
        shared_config=SharedConfig(
            base_request_http={
                "user_id": "u",
                "reqId": "r",
                "items": [],
            },
            common_assertions=["共享断言暂不可解析"],
        ),
        cases=[
            ParsedTestCase(
                id="TC-DEMO-001",
                title="共享断言统计",
                priority="P1",
                assertions=[],
            )
        ],
    )

    result = emit_file(
        parse_result,
        "business",
        output_dir=tmp_path,
        project=load_project_config(),
    )

    assert result.diagnostics == []
    assert result.unparsed == [("TC-DEMO-001", "共享断言暂不可解析")]


def test_real_profile_case_flow_strategy_for_validation_pilot():
    flows = load_profile_case_flows(_profile("validation_ratelimit"))
    assert set(flows) >= {
        "TC-VAL-001",
        "TC-VAL-002",
        "TC-VAL-003",
        "TC-VAL-005",
        "TC-GRPC-001",
        "TC-GRPC-002",
        "TC-GRPC-003",
        "TC-SCHEMA-001",
        "TC-SCHEMA-002",
        "TC-SCHEMA-003",
    }

    parse_result = parse_case_file("test_workspace/cases/validation_ratelimit/business.md")
    file_ir = build_file_ir(
        parse_result,
        "business",
        profile_path=_profile("validation_ratelimit"),
        project=load_project_config(),
    )

    case_ir = _case(file_ir, "TC-VAL-001")

    assert case_ir.strategy == "structured_case_flow"
    assert case_ir.protocol == "flow"
    assert case_ir.fixtures == ["setup_validation_ratelimit"]
    assert case_ir.custom_body is None
    assert case_ir.case_flow is not None
    assert case_ir.case_flow.object_name == "client_factory"
    assert case_ir.case_flow.steps[0].call == "client_factory"

    grpc_case_ir = _case(file_ir, "TC-GRPC-001")
    assert grpc_case_ir.strategy == "structured_case_flow"
    assert grpc_case_ir.case_flow is not None
    assert grpc_case_ir.case_flow.steps[1].call == "case.grpc_missing"

    schema_case_ir = _case(file_ir, "TC-SCHEMA-001")
    assert schema_case_ir.strategy == "structured_case_flow"
    assert schema_case_ir.case_flow is not None
    assert schema_case_ir.case_flow.steps[5].kind == "assign"
    assert schema_case_ir.case_flow.steps[5].target == "locs"


def test_emitter_renders_validation_case_flow_without_output_diff(tmp_path):
    results = emit_module("validation_ratelimit", output_dir=tmp_path)

    assert not any(result.diagnostics for result in results)
    for name in (
        "test_validation_ratelimit_business.py",
        "test_validation_ratelimit_boundary.py",
    ):
        generated = Path("test_workspace/tests/generated") / name
        emitted = tmp_path / name
        assert emitted.read_text(encoding="utf-8") == generated.read_text(encoding="utf-8")


def test_emitter_allows_case_flow_without_base_request(tmp_path):
    parse_result = parse_case_file("test_workspace/cases/ab_service/business.md")

    result = emit_file(
        parse_result,
        "business",
        profile_path=_profile("ab_service"),
        output_dir=tmp_path,
    )

    assert result.diagnostics == []
    text = (tmp_path / "test_ab_service_business.py").read_text(encoding="utf-8")
    assert "def test_tc_abs_001(self, setup_ab_service):" in text
    assert 'resp = ab.get("/health")' in text


def test_module_type_requirement_accepts_case_flows(tmp_path):
    profile_path = tmp_path / "codegen_profile_demo.md"
    profile_path.write_text(
        """```yaml
module_type: multi_endpoint
case_flows:
  TC-DEMO-001:
    fixture: setup_demo
    steps:
      - call: setup_demo
        save_as: case
      - call: case.get
        args: ["/health"]
        save_as: resp
      - assert: "assert resp.status_code == 200"
```
""",
        encoding="utf-8",
    )
    parse_result = ParseResult(
        module="demo",
        source_file="test_workspace/cases/demo/business.md",
        shared_config=SharedConfig(base_request_http=None),
        cases=[
            ParsedTestCase(
                id="TC-DEMO-001",
                title="多端点结构化流程",
                priority="P1",
                assertions=["`status_code == 200`"],
                section="健康检查",
            )
        ],
    )

    result = emit_file(
        parse_result,
        "business",
        profile_path=profile_path,
        output_dir=tmp_path,
        project=load_project_config(),
    )

    assert result.diagnostics == []


def test_case_flow_profile_validation_rejects_forward_refs():
    errors = validate_case_flows({
        "TC-DEMO-001": {
            "fixture": "setup_demo",
            "steps": [
                {"call": "case.post", "args": [{"ref": "missing"}], "save_as": "resp"},
            ],
        }
    })

    assert any("must reference a previous save_as" in error for error in errors)


def test_profile_strategy_validation_rejects_case_body_case_flow_overlap():
    errors = validate_profile_strategy_conflicts(
        {"TC-DEMO-001": ["resp = case.http()"]},
        {"TC-DEMO-001": {"fixture": "setup_demo", "steps": []}},
    )

    assert any("defined in both case_bodies and case_flows" in error for error in errors)


def test_emit_file_rejects_case_body_case_flow_overlap(tmp_path):
    profile_path = tmp_path / "codegen_profile_demo.md"
    profile_path.write_text(
        """```yaml
case_bodies:
  TC-DEMO-001: |
    resp = case.http()
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
    parse_result = ParseResult(
        module="demo",
        source_file="test_workspace/cases/demo/business.md",
        shared_config=SharedConfig(base_request_http={"user_id": "", "reqId": ""}),
        cases=[
            ParsedTestCase(
                id="TC-DEMO-001",
                title="重叠策略",
                priority="P1",
                section="策略",
            )
        ],
    )

    result = emit_file(
        parse_result,
        "business",
        profile_path=profile_path,
        output_dir=tmp_path,
    )

    assert any("defined in both case_bodies and case_flows" in d for d in result.diagnostics)


def test_case_flow_profile_validation_rejects_bare_assert_expression():
    errors = validate_case_flows({
        "TC-DEMO-001": {
            "fixture": "setup_demo",
            "steps": [
                {"call": "setup_demo", "save_as": "case"},
                {"assert": "`resp == ERR`"},
            ],
        }
    })

    assert any("must start with 'assert '" in error for error in errors)


def test_case_flow_profile_validation_accepts_assign_step():
    errors = validate_case_flows({
        "TC-DEMO-001": {
            "fixture": "setup_demo",
            "steps": [
                {"call": "setup_demo", "save_as": "case"},
                {"assign": "locs", "expr": "[item['loc'] for item in detail]"},
                {"comment": "MANUAL CHECK: inspect logs"},
                {"assert": "assert ['body', 'external'] in locs"},
            ],
        }
    })

    assert errors == []


def test_case_flow_defaults_expand_fixture_object_and_setup_step(tmp_path):
    profile_path = tmp_path / "codegen_profile_demo.md"
    profile_path.write_text(
        """```yaml
default_fixture: setup_demo
default_object: client_factory
default_case_setup:
  call: client_factory
  kwargs:
    case_id: "{case_id}"
  save_as: case
case_flows:
  TC-DEMO-001:
    steps:
      - call: case.get
        args: ["/health"]
        save_as: resp
      - assert: 'assert resp["status"] == "ok"'
```
""",
        encoding="utf-8",
    )
    parse_result = ParseResult(
        module="demo",
        source_file="test_workspace/cases/demo/business.md",
        shared_config=SharedConfig(base_request_http={"user_id": "", "reqId": ""}),
        cases=[
            ParsedTestCase(
                id="TC-DEMO-001",
                title="默认 case setup",
                priority="P1",
                assertions=['`resp["status"] == "ok"`'],
                section="流程",
            )
        ],
    )

    file_ir = build_file_ir(
        parse_result,
        "business",
        profile_path=profile_path,
        project=load_project_config(),
    )
    case_ir = _case(file_ir, "TC-DEMO-001")

    assert case_ir.fixtures == ["setup_demo"]
    assert case_ir.case_flow is not None
    assert case_ir.case_flow.object_name == "client_factory"
    assert case_ir.case_flow.steps[0].call == "client_factory"
    assert case_ir.case_flow.steps[0].kwargs == {"case_id": "TC-DEMO-001"}
    assert case_ir.case_flow.steps[0].save_as == "case"
    assert case_ir.case_flow.steps[1].call == "case.get"


def test_emitter_can_render_structured_case_flow(tmp_path):
    profile_path = tmp_path / "codegen_profile_demo.md"
    profile_path.write_text(
        """```yaml
case_flows:
  TC-DEMO-001:
    fixture: setup_demo
    object: case
    steps:
      - call: case.http
        args: ["u_demo"]
        kwargs:
          req_id: "req-demo"
        save_as: resp
      - assign: locs
        expr: "[item[\\\"loc\\\"] for item in resp[\\\"detail\\\"]]"
      - comment: "MANUAL CHECK: inspect logs"
      - assert: "assert resp[\\\"code\\\"] == 0"
```
""",
        encoding="utf-8",
    )
    parse_result = ParseResult(
        module="demo",
        source_file="test_workspace/cases/demo/business.md",
        shared_config=SharedConfig(base_request_http={"user_id": "", "reqId": ""}),
        cases=[
            ParsedTestCase(
                id="TC-DEMO-001",
                title="结构化流程",
                priority="P1",
                assertions=["`resp[\"code\"] == 0`"],
                section="流程",
            )
        ],
    )

    result = emit_file(
        parse_result,
        "business",
        profile_path=profile_path,
        output_dir=tmp_path,
    )

    assert result.diagnostics == []
    text = (tmp_path / "test_demo_business.py").read_text(encoding="utf-8")
    assert "def test_tc_demo_001(self, setup_demo):" in text
    assert "case = setup_demo" in text
    assert 'resp = case.http("u_demo", req_id="req-demo")' in text
    assert 'locs = [item["loc"] for item in resp["detail"]]' in text
    assert "# MANUAL CHECK: inspect logs" in text
    assert 'assert resp["code"] == 0' in text
