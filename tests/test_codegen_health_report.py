from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from aitest_kit.codegen.cli import codegen
from aitest_kit.codegen.health import build_suite_codegen_health_report, codegen_health_to_dict
from aitest_kit.codegen.suite import load_suite_context_for_paths


def _write_suite_workspace(root: Path) -> Path:
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
  helper_dir: test_workspace/targets/sub2api/helpers
  profile_dir: test_workspace/targets/sub2api/profiles
  suite_dir: test_workspace/suites/sub2api
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
    (profile_dir / "profile_gateway_api.md").write_text(
        """```yaml
module_type: multi_endpoint
default_fixture: setup_gateway_api
default_object: client
```
""",
        encoding="utf-8",
    )
    (fixture_dir / "gateway_api.py").write_text(
        """def setup_gateway_api():
    return object()
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

### TC-GW-001：health ok
- **优先级**：P0
- **断言**：`response.status == "ok"`

### TC-GW-002：body escape
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
case_flows:
  TC-GW-001:
    fixture: setup_gateway_api
    object: client
    steps:
      - call: client.health
        save_as: resp
      - assert: 'assert resp["status"] == "ok"'
case_bodies:
  TC-GW-002: |
    assert True
```
""",
        encoding="utf-8",
    )
    return suite_dir / "suite.yaml"


def test_codegen_health_report_counts_case_flow_and_case_body(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    suite_file = _write_suite_workspace(tmp_path)
    context = load_suite_context_for_paths(suite_file)

    report = build_suite_codegen_health_report(context)
    payload = codegen_health_to_dict(report)
    module = payload["modules"][0]

    assert payload["module_count"] == 1
    assert module["module"] == "gateway_api"
    assert module["suite"] == "gateway_smoke"
    assert module["case_flow_count"] == 1
    assert module["case_body_count"] == 1
    assert module["maturity"] == "L3"
    assert module["profile_errors"] == 0


def test_codegen_health_report_cli_writes_artifacts(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        root = Path(cwd)
        suite_file = _write_suite_workspace(root)
        report_dir = root / "reports"

        result = runner.invoke(
            codegen,
            [
                "--suite-file",
                str(suite_file),
                "--health-report",
                "--write-report",
                "--report-dir",
                str(report_dir),
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Codegen health artifacts written:" in result.output
        assert (report_dir / "codegen_health_report.md").exists()
        json_path = report_dir / "codegen_health_report.json"
        assert json_path.exists()
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["modules"][0]["module"] == "gateway_api"
        assert payload["modules"][0]["suite"] == "gateway_smoke"
