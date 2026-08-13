from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from aitest_kit.codegen.cli import codegen
from aitest_kit.codegen.health import build_suite_codegen_health_report, codegen_health_to_dict
from aitest_kit.codegen.suite import load_suite_context_for_paths


def _write_suite_workspace(root: Path) -> Path:
    target_dir = root / "test_workspace" / "targets" / "sub2api"
    module_dir = target_dir / "modules" / "gateway_api"
    suite_dir = root / "test_workspace" / "suites" / "sub2api" / "gateway_smoke"
    module_dir.mkdir(parents=True, exist_ok=True)
    suite_dir.mkdir(parents=True, exist_ok=True)
    for package_dir in (
        root / "test_workspace",
        root / "test_workspace" / "targets",
        target_dir,
        target_dir / "modules",
        module_dir,
    ):
        (package_dir / "__init__.py").write_text("", encoding="utf-8")

    (target_dir / "target.yaml").write_text(
        """target: sub2api
defaults:
  module_dir: test_workspace/targets/sub2api/modules
  helper_dir: test_workspace/targets/sub2api/helpers
  suite_dir: test_workspace/suites/sub2api
  generated_dir: test_workspace/generated/sub2api
  reports_dir: test_workspace/reports/sub2api
""",
        encoding="utf-8",
    )
    (module_dir / "module.yaml").write_text(
        """target: sub2api
module: gateway_api
module_type: multi_endpoint
""",
        encoding="utf-8",
    )
    (module_dir / "profile.md").write_text(
        "```yaml\n{}\n```\n",
        encoding="utf-8",
    )
    (module_dir / "harness.py").write_text(
        """class GatewayApiHarness:
    def health(self, **kwargs):
        return {"status": "ok", **kwargs}
""",
        encoding="utf-8",
    )
    (module_dir / "fixture.py").write_text(
        """import pytest

from .harness import GatewayApiHarness


@pytest.fixture
def setup_gateway_api() -> GatewayApiHarness:
    return GatewayApiHarness()
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

**基础请求体（HTTP）**：

```json
{"status": 1, "token": "placeholder"}
```

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
variables:
  defaults:
    expected_status:
      value: 0
  cases:
    TC-GW-001:
      auth_token:
        env: SUB2API_USER_TOKEN
requests:
  TC-GW-001:
    patches:
      - op: replace
        path: /status
        value_from: expected_status
      - op: replace
        path: /token
        value_from: auth_token
case_flows:
  TC-GW-001:
    steps:
      - call: harness.health
        kwargs:
          body: {request_ref: self}
        save_as: resp
      - assert: 'assert resp["status"] == "ok"'
structured_assertions:
  TC-GW-001:
    - type: jsonpath_equals
      target: resp
      path: $.status
      equals: ok
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
    assert module["structured_assertion_target_counts"] == {"resp": 1}
    assert module["request_binding_counts"]["profile.requests.patches"] == 1
    assert module["request_binding_counts"]["profile.requests.patches.value_from"] == 1
    assert module["profile_variable_counts"]["profile.variables.usage"] == 2
    assert module["profile_variable_counts"]["profile.variables.value"] == 1
    assert module["profile_variable_counts"]["profile.variables.env"] == 1
    assert module["profile_variable_counts"]["profile.variables.defaults"] == 1
    assert module["profile_variable_counts"]["profile.variables.cases"] == 1
    assert any("SUB2API_USER_TOKEN" in item["message"] for item in module["review_focus"])
    assert any(item["kind"] == "request_patch_variable" for item in module["review_focus"])
    assert module["case_body_cases"][0]["case_id"] == "TC-GW-002"
    assert module["structured_assertion_cases"][0]["case_id"] == "TC-GW-001"
    assert module["next_actions"]


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
        assert payload["modules"][0]["structured_assertion_target_counts"] == {"resp": 1}
        assert payload["modules"][0]["profile_variable_counts"]["profile.variables.env"] == 1
        assert any("SUB2API_USER_TOKEN" in item["message"] for item in payload["modules"][0]["review_focus"])
        assert "P1: review 1 case_body case(s)" in "\n".join(payload["modules"][0]["next_actions"])
