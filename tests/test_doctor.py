from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from aitest_kit.cli import main


def _write_flow_module(workspace: Path) -> None:
    case_dir = workspace / "test_workspace" / "cases" / "demo"
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "business.md").write_text(
        """# demo 业务测试用例

## 共享配置

**接口**：`GET /health`

**基础请求体（HTTP）**：

```json
{
  "user_id": "u_default",
  "reqId": "req_default"
}
```

---

## 一、基础场景

### TC-DEMO-001：demo flow case
- **优先级**：P1
- **断言**：`response.status == "ok"`
""",
        encoding="utf-8",
    )

    fixture_dir = workspace / "test_workspace" / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "demo.py").write_text(
        """from __future__ import annotations

import os

import pytest


class DemoClient:
    def health(self) -> dict:
        return {"status": "ok"}


@pytest.fixture
def setup_demo() -> DemoClient:
    os.environ.get("DEMO_BASE_URL")
    return DemoClient()
""",
        encoding="utf-8",
    )
    (fixture_dir / "codegen_profile_demo.md").write_text(
        """```yaml
module_type: multi_endpoint
extra_imports:
  - "from test_workspace.tests.fixtures.demo import setup_demo"
case_flows:
  TC-DEMO-001:
    fixture: setup_demo
    object: client
    steps:
      - call: client.health
        save_as: resp
      - assert: 'assert resp["status"] == "ok"'
```
""",
        encoding="utf-8",
    )


def test_doctor_reports_empty_workspace_with_warnings(tmp_path):
    target = tmp_path / "project"
    runner = CliRunner()
    init_result = runner.invoke(main, ["init", "--target", str(target)])
    assert init_result.exit_code == 0

    result = runner.invoke(main, ["doctor", "--workspace", str(target)])

    assert result.exit_code == 0
    assert "AITest Doctor" in result.output
    assert "[OK] workspace layout" in result.output
    assert "[WARN] modules: no modules found under test_workspace/cases" in result.output
    assert "[WARN] pytest collect: no generated pytest files found" in result.output
    assert "fail=0" in result.output


def test_doctor_passes_generated_flow_module(tmp_path):
    target = tmp_path / "project"
    runner = CliRunner()
    init_result = runner.invoke(main, ["init", "--target", str(target)])
    assert init_result.exit_code == 0
    _write_flow_module(target)

    generate = runner.invoke(main, ["codegen", "demo", "--workspace", str(target)])
    assert generate.exit_code == 0, generate.output

    result = runner.invoke(main, ["doctor", "--workspace", str(target), "--module", "demo"])

    assert result.exit_code == 0, result.output
    assert "[OK] modules: found module: demo" in result.output
    assert "[OK] profile gate: passed" in result.output
    assert "[OK] generated freshness: passed" in result.output
    assert "[OK] pytest collect: passed" in result.output
    assert "DEMO_BASE_URL" in result.output
    assert "fail=0" in result.output


def test_doctor_warns_when_fixture_module_is_not_registered(tmp_path):
    target = tmp_path / "project"
    runner = CliRunner()
    init_result = runner.invoke(main, ["init", "--target", str(target)])
    assert init_result.exit_code == 0
    _write_flow_module(target)
    generate = runner.invoke(main, ["codegen", "demo", "--workspace", str(target)])
    assert generate.exit_code == 0, generate.output

    conftest = target / "test_workspace" / "tests" / "conftest.py"
    conftest.write_text('"""No fixture plugin registration."""\n', encoding="utf-8")

    result = runner.invoke(main, ["doctor", "--workspace", str(target)])

    assert result.exit_code == 0, result.output
    assert "[WARN] fixture registration" in result.output
    assert "test_workspace.tests.fixtures.demo" in result.output
    assert "fail=0" in result.output


def test_doctor_checks_case_suite_profiles(tmp_path):
    target = tmp_path / "project"
    runner = CliRunner()
    init_result = runner.invoke(main, ["init", "--target", str(target)])
    assert init_result.exit_code == 0

    fixture_dir = target / "test_workspace" / "tests" / "fixtures"
    (fixture_dir / "codegen_profile_demo.md").write_text(
        """```yaml
module_type: multi_endpoint
```
""",
        encoding="utf-8",
    )
    suite_dir = target / "test_workspace" / "casesuites" / "demo_smoke"
    suite_dir.mkdir(parents=True, exist_ok=True)
    (suite_dir / "aitest_suite.yaml").write_text(
        """module: demo
suite: demo_smoke
case_files:
  - smoke.md
profile: codegen_profile_demo_smoke_suite.md
""",
        encoding="utf-8",
    )
    (suite_dir / "smoke.md").write_text(
        """# smoke

## 共享配置

**接口**：`GET /health`

---

## 一、冒烟

### TC-DEMO-001：health
- **优先级**：P0
- **断言**：`response.status == "ok"`
""",
        encoding="utf-8",
    )
    (suite_dir / "codegen_profile_demo_smoke_suite.md").write_text(
        """```yaml
profile_scope: case_suite
parent_module: demo
suite: demo_smoke
case_flows:
  TC-DEMO-001:
    fixture: setup_demo
    object: client
    steps:
      - call: client.health
        save_as: resp
      - assert: 'assert resp["status"] == "ok"'
```
""",
        encoding="utf-8",
    )

    result = runner.invoke(main, ["doctor", "--workspace", str(target)])

    assert result.exit_code == 0, result.output
    assert "[OK] case suites: 1 suite(s) valid" in result.output
    assert "fail=0" in result.output


def test_doctor_fails_unknown_module(tmp_path):
    target = tmp_path / "project"
    runner = CliRunner()
    init_result = runner.invoke(main, ["init", "--target", str(target)])
    assert init_result.exit_code == 0

    result = runner.invoke(main, ["doctor", "--workspace", str(target), "--module", "missing"])

    assert result.exit_code == 1
    assert "[FAIL] modules: module not found under test_workspace/cases: missing" in result.output
