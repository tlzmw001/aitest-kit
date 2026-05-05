from click.testing import CliRunner

from aitest_kit.codegen.cli import codegen
from aitest_kit.codegen.promotion import analyze_case_body_promotion


def test_promotion_analysis_groups_repeated_helper_calls(tmp_path):
    profile_path = tmp_path / "codegen_profile_demo.md"
    profile_path.write_text(
        """```yaml
case_bodies:
  TC-DEMO-001: |
    case = setup_demo(case_id="TC-DEMO-001")
    resp = case.http("u1")
    assert resp["code"] == 0
  TC-DEMO-002: |
    case = setup_demo(case_id="TC-DEMO-002")
    resp = case.http("u2")
    assert resp["code"] == 0
  TC-DEMO-003: |
    case = setup_demo(case_id="TC-DEMO-003")
    resp = case.http("u3")
    assert resp["code"] == 0
  TC-DEMO-004: |
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(case.http, ["u4", "u5"]))
```
""",
        encoding="utf-8",
    )
    report = analyze_case_body_promotion(
        "demo",
        profile_path,
    )

    candidates = [
        group for group in report.groups
        if group.target == "promote_to_case_flow" and group.candidate
    ]

    assert report.total_case_bodies == 4
    assert any("TC-DEMO-001" in group.case_ids for group in candidates)
    assert any("http" in group.methods for group in candidates)
    assert any(group.target == "keep_case_body" for group in report.groups)


def test_promotion_analysis_uses_profile_object_names(tmp_path):
    profile_path = tmp_path / "codegen_profile_demo.md"
    profile_path.write_text(
        """```yaml
case_flows:
  TC-DEMO-010:
    fixture: setup_demo
    object: api
    steps:
      - call: api.get
        args: ["/health"]
        save_as: resp
      - assert: "assert resp.status_code == 200"
case_bodies:
  TC-DEMO-001: |
    resp = api.get("/orders/1")
    assert resp.status_code == 200
  TC-DEMO-002: |
    resp = api.get("/orders/2")
    assert resp.status_code == 200
  TC-DEMO-003: |
    resp = api.get("/orders/3")
    assert resp.status_code == 200
```
""",
        encoding="utf-8",
    )
    report = analyze_case_body_promotion("demo", profile_path)

    candidates = [
        group for group in report.groups
        if group.target == "promote_to_case_flow" and group.candidate
    ]

    assert any("get" in group.methods for group in candidates)
    assert any("TC-DEMO-001" in group.case_ids for group in candidates)


def test_codegen_analyze_promotion_is_read_only_report():
    result = CliRunner().invoke(codegen, ["ab_service", "--analyze-promotion"])

    assert result.exit_code == 0
    assert "promotion_reports:" in result.output
    assert "module: ab_service" in result.output
    assert "keep_case_body" in result.output
