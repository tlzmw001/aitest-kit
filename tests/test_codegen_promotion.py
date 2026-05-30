from pathlib import Path

from click.testing import CliRunner

from aitest_kit.codegen.cli import codegen
from aitest_kit.codegen.promotion import analyze_case_body_promotion


def _write_promotion_suite(root):
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


def test_promotion_analysis_groups_repeated_helper_calls(tmp_path):
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
    profile_path = tmp_path / "profile_demo_suite.md"
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


def test_codegen_analyze_promotion_is_read_only_report(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        suite_file = _write_promotion_suite(Path(cwd))
        result = runner.invoke(codegen, ["--suite-file", str(suite_file), "--analyze-promotion"])

        assert result.exit_code == 0, result.output
        assert "promotion_reports:" in result.output
        assert "module: gateway_api" in result.output
        assert "promote_to_case_flow" in result.output
