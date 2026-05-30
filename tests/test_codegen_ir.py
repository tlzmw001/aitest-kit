from __future__ import annotations

import json
from pathlib import Path

from aitest_kit.codegen.emitter import emit_file
from aitest_kit.codegen.ir import ir_to_dict
from aitest_kit.codegen.parser import ParseResult, SharedConfig, TestCase as ParsedTestCase
from aitest_kit.codegen.planner import build_file_ir
from aitest_kit.codegen.profile import (
    validate_case_flows,
    validate_profile_strategy_conflicts,
)
from aitest_kit.codegen.project_config import ProjectConfig, load_project_config


def _case(file_ir, case_id: str):
    for case_ir in file_ir.cases:
        if case_ir.case_id == case_id:
            return case_ir
    raise AssertionError(f"{case_id} not found")


def _write_profile(path: Path, yaml_body: str) -> None:
    path.write_text(f"```yaml\n{yaml_body}```\n", encoding="utf-8")


def _parse_result(
    *,
    module: str = "demo",
    case_id: str = "TC-DEMO-001",
    assertions: list[str] | None = None,
    base_request_http: dict | None = None,
) -> ParseResult:
    return ParseResult(
        module=module,
        source_file=f"test_workspace/suites/demo/demo_suite/{module}.md",
        shared_config=SharedConfig(base_request_http=base_request_http),
        cases=[
            ParsedTestCase(
                id=case_id,
                title="demo case",
                priority="P1",
                assertions=assertions or [],
                section="流程",
            )
        ],
    )


def test_ir_marks_profile_case_flow_without_default_request_plan(tmp_path):
    profile_path = tmp_path / "profile_demo_suite.md"
    _write_profile(
        profile_path,
        """case_flows:
  TC-DEMO-001:
    fixture: setup_demo
    object: client
    steps:
      - call: client.health
        save_as: resp
      - assert: 'assert resp["status"] == "ok"'
""",
    )

    file_ir = build_file_ir(
        _parse_result(assertions=['`response.status == "ok"`']),
        "business",
        profile_path=profile_path,
        project=load_project_config(),
    )
    case_ir = _case(file_ir, "TC-DEMO-001")

    assert case_ir.strategy == "structured_case_flow"
    assert case_ir.protocol == "flow"
    assert case_ir.request is None
    assert case_ir.call is None
    assert case_ir.fixtures == ["setup_demo"]
    assert case_ir.case_flow is not None
    assert case_ir.case_flow.steps[0].call == "client.health"


def test_ir_serializes_to_plain_json_data(tmp_path):
    profile_path = tmp_path / "profile_demo_suite.md"
    _write_profile(
        profile_path,
        """case_flows:
  TC-DEMO-001:
    fixture: setup_demo
    object: client
    steps:
      - assert: 'assert True'
""",
    )
    file_ir = build_file_ir(
        _parse_result(),
        "business",
        profile_path=profile_path,
        project=load_project_config(),
    )

    payload = ir_to_dict(_case(file_ir, "TC-DEMO-001"))

    assert payload["case_id"] == "TC-DEMO-001"
    assert payload["strategy"] == "structured_case_flow"
    json.dumps(payload, ensure_ascii=False)


def test_emitter_reports_unparsed_common_assertions(tmp_path):
    parse_result = ParseResult(
        module="demo",
        source_file="test_workspace/suites/demo/demo_suite/business.md",
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


def test_module_type_requirement_accepts_case_flows(tmp_path):
    profile_path = tmp_path / "profile_demo_suite.md"
    _write_profile(
        profile_path,
        """module_type: multi_endpoint
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
""",
    )

    result = emit_file(
        _parse_result(assertions=["`status_code == 200`"]),
        "business",
        profile_path=profile_path,
        output_dir=tmp_path,
        project=load_project_config(),
    )

    assert result.diagnostics == []


def test_module_type_requirement_requires_profile_or_module_yaml_injected_type(tmp_path):
    profile_path = tmp_path / "profile_demo_suite.md"
    _write_profile(
        profile_path,
        """module_type: isolated_service
extra_imports: []
""",
    )
    project = ProjectConfig(
        module_types={"isolated_service": {"requires": ["case_bodies"]}},
    )

    result = emit_file(
        _parse_result(base_request_http={"user_id": "", "reqId": ""}),
        "business",
        profile_path=profile_path,
        output_dir=tmp_path,
        project=project,
    )

    assert any("module_type=isolated_service requires case_bodies or case_flows" in d for d in result.diagnostics)
    assert not (tmp_path / "test_demo_business.py").exists()


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
    profile_path = tmp_path / "profile_demo_suite.md"
    _write_profile(
        profile_path,
        """case_bodies:
  TC-DEMO-001: |
    resp = case.http()
case_flows:
  TC-DEMO-001:
    fixture: setup_demo
    steps:
      - call: setup_demo
        save_as: case
      - assert: "assert True"
""",
    )

    result = emit_file(
        _parse_result(),
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
    profile_path = tmp_path / "profile_demo_suite.md"
    _write_profile(
        profile_path,
        """default_fixture: setup_demo
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
""",
    )

    file_ir = build_file_ir(
        _parse_result(assertions=['`resp["status"] == "ok"`']),
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
    profile_path = tmp_path / "profile_demo_suite.md"
    _write_profile(
        profile_path,
        """case_flows:
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
""",
    )

    result = emit_file(
        _parse_result(assertions=["`resp[\"code\"] == 0`"], base_request_http={"user_id": "", "reqId": ""}),
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
