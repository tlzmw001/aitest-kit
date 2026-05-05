import json
from pathlib import Path

from click.testing import CliRunner

from aitest_kit.codegen.cli import codegen
from aitest_kit.codegen.health import build_codegen_health_report, codegen_health_to_dict


def test_codegen_health_report_counts_case_flow_and_case_body():
    report = build_codegen_health_report(["ab_service"], cases_dir=Path("test_workspace/cases"))
    payload = codegen_health_to_dict(report)
    module = payload["modules"][0]

    assert payload["module_count"] == 1
    assert module["module"] == "ab_service"
    assert module["case_flow_count"] == 26
    assert module["case_body_count"] == 14
    assert module["maturity"] == "L3"
    assert module["profile_errors"] == 0


def test_codegen_health_report_cli_writes_artifacts(tmp_path):
    report_dir = tmp_path / "reports"
    result = CliRunner().invoke(
        codegen,
        ["ab_service", "--health-report", "--write-report", "--report-dir", str(report_dir)],
    )

    assert result.exit_code == 0
    assert "Codegen health artifacts written:" in result.output
    assert (report_dir / "codegen_health_report.md").exists()
    json_path = report_dir / "codegen_health_report.json"
    assert json_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["modules"][0]["module"] == "ab_service"
