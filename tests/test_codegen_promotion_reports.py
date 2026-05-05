import json
from pathlib import Path

from click.testing import CliRunner

from aitest_kit.codegen.cli import codegen
from aitest_kit.codegen.promotion import (
    analyze_case_body_promotion,
    write_promotion_patch,
    write_promotion_report,
)


def _demo_profile(tmp_path: Path) -> Path:
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
```
""",
        encoding="utf-8",
    )
    return profile_path


def test_write_promotion_report_outputs_markdown_and_json(tmp_path):
    profile_path = _demo_profile(tmp_path)
    report = analyze_case_body_promotion("demo", profile_path)
    paths = write_promotion_report(report, tmp_path / "reports")

    markdown = paths["markdown"].read_text(encoding="utf-8")
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))

    assert paths["markdown"].name == "demo_promotion_report.md"
    assert paths["json"].name == "demo_promotion_report.json"
    assert "Codegen Promotion Report: demo" in markdown
    assert "review for case_flow promotion" in markdown
    assert payload["module"] == "demo"
    assert payload["groups"][0]["objects"] == ["case"]


def test_write_promotion_patch_outputs_review_markdown_and_diff(tmp_path):
    profile_path = _demo_profile(tmp_path)
    report = analyze_case_body_promotion("demo", profile_path)
    paths = write_promotion_patch(
        report,
        tmp_path / "reports",
        profile_path=profile_path,
    )

    markdown = paths["markdown"].read_text(encoding="utf-8")
    diff = paths["diff"].read_text(encoding="utf-8")

    assert paths["markdown"].name == "demo_promotion_patch.md"
    assert paths["diff"].name == "demo_promotion_patch.diff"
    assert "Codegen Promotion Patch Draft: demo" in markdown
    assert "TC-DEMO-001, TC-DEMO-002, TC-DEMO-003" in markdown
    assert "--- a/" in diff
    assert "Review-only promotion notes" in diff


def test_codegen_analyze_promotion_can_write_report_files(tmp_path):
    out_dir = tmp_path / "codegen-reports"
    result = CliRunner().invoke(
        codegen,
        ["ab_service", "--analyze-promotion", "--write-report", "--report-dir", str(out_dir)],
    )

    assert result.exit_code == 0
    assert "promotion_reports:" in result.output
    assert "Promotion artifacts written:" in result.output
    assert (out_dir / "ab_service_promotion_report.md").exists()
    assert (out_dir / "ab_service_promotion_report.json").exists()


def test_codegen_suggest_promotion_patch_writes_patch_files(tmp_path):
    out_dir = tmp_path / "codegen-reports"
    result = CliRunner().invoke(
        codegen,
        ["ab_service", "--suggest-promotion-patch", "--report-dir", str(out_dir)],
    )

    assert result.exit_code == 0
    assert "Promotion artifacts written:" in result.output
    assert (out_dir / "ab_service_promotion_report.md").exists()
    assert (out_dir / "ab_service_promotion_report.json").exists()
    assert (out_dir / "ab_service_promotion_patch.md").exists()
    assert (out_dir / "ab_service_promotion_patch.diff").exists()
