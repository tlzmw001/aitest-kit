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
    profile_path = tmp_path / "profile_demo_suite.md"
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


def _write_promotion_suite(root: Path) -> Path:
    target_dir = root / "test_workspace" / "targets" / "sub2api"
    module_dir = target_dir / "modules"
    fixture_dir = target_dir / "fixtures"
    profile_dir = target_dir / "profiles"
    suite_dir = root / "test_workspace" / "suites" / "sub2api" / "gateway_smoke"
    module_dir.mkdir(parents=True, exist_ok=True)
    fixture_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)
    suite_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "target.yaml").write_text(
        """target: sub2api
defaults:
  module_dir: test_workspace/targets/sub2api/modules
  fixture_dir: test_workspace/targets/sub2api/fixtures
  profile_dir: test_workspace/targets/sub2api/profiles
  generated_dir: test_workspace/generated/sub2api
  reports_dir: test_workspace/reports/sub2api
""",
        encoding="utf-8",
    )
    (module_dir / "gateway_api.yaml").write_text(
        """target: sub2api
module: gateway_api
module_type: multi_endpoint
fixture:
  file: gateway_api.py
  default_fixture: setup_gateway_api
""",
        encoding="utf-8",
    )
    (fixture_dir / "gateway_api.py").write_text("def setup_gateway_api():\n    return object()\n", encoding="utf-8")
    (profile_dir / "profile_gateway_api.md").write_text(
        """```yaml
module_type: multi_endpoint
default_fixture: setup_gateway_api
default_object: client
```
""",
        encoding="utf-8",
    )
    (suite_dir / "suite.yaml").write_text(
        """target: sub2api
module: gateway_api
suite: gateway_smoke
case_files:
  - business.md
""",
        encoding="utf-8",
    )
    (suite_dir / "business.md").write_text(
        """# gateway smoke

## 共享配置

**通用断言**：`response.code == 0`

---

## 一、冒烟

### TC-GW-001：case 1
- **优先级**：P1
- **断言**：`response.code == 0`

### TC-GW-002：case 2
- **优先级**：P1
- **断言**：`response.code == 0`

### TC-GW-003：case 3
- **优先级**：P1
- **断言**：`response.code == 0`
""",
        encoding="utf-8",
    )
    (suite_dir / "profile_gateway_smoke_suite.md").write_text(
        """```yaml
profile_scope: case_suite
parent_module: gateway_api
suite: gateway_smoke
case_bodies:
  TC-GW-001: |
    resp = client.get("/orders/1")
    assert resp.status_code == 200
  TC-GW-002: |
    resp = client.get("/orders/2")
    assert resp.status_code == 200
  TC-GW-003: |
    resp = client.get("/orders/3")
    assert resp.status_code == 200
```
""",
        encoding="utf-8",
    )
    return suite_dir / "suite.yaml"


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
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        root = Path(cwd)
        suite_file = _write_promotion_suite(root)
        out_dir = root / "codegen-reports"
        result = runner.invoke(
            codegen,
            [
                "--suite-file",
                str(suite_file),
                "--analyze-promotion",
                "--write-report",
                "--report-dir",
                str(out_dir),
            ],
        )

        assert result.exit_code == 0, result.output
        assert "promotion_reports:" in result.output
        assert "Promotion artifacts written:" in result.output
        assert (out_dir / "gateway_api_gateway_smoke_promotion_report.md").exists()
        assert (out_dir / "gateway_api_gateway_smoke_promotion_report.json").exists()


def test_codegen_suggest_promotion_patch_writes_patch_files(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        root = Path(cwd)
        suite_file = _write_promotion_suite(root)
        out_dir = root / "codegen-reports"
        result = runner.invoke(
            codegen,
            [
                "--suite-file",
                str(suite_file),
                "--suggest-promotion-patch",
                "--report-dir",
                str(out_dir),
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Promotion artifacts written:" in result.output
        assert (out_dir / "gateway_api_gateway_smoke_promotion_report.md").exists()
        assert (out_dir / "gateway_api_gateway_smoke_promotion_report.json").exists()
        assert (out_dir / "gateway_api_gateway_smoke_promotion_patch.md").exists()
        assert (out_dir / "gateway_api_gateway_smoke_promotion_patch.diff").exists()
