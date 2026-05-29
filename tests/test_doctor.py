from __future__ import annotations

from click.testing import CliRunner

from aitest_kit.cli import main


def test_doctor_reports_empty_workspace_with_warnings(tmp_path):
    target = tmp_path / "project"
    runner = CliRunner()
    init_result = runner.invoke(main, ["init", "--target", str(target)])
    assert init_result.exit_code == 0

    result = runner.invoke(main, ["doctor", "--workspace", str(target)])

    assert result.exit_code == 0
    assert "AITest Doctor" in result.output
    assert "[OK] workspace layout" in result.output
    assert "[WARN] case suites: no suite.yaml files found under test_workspace/suites" in result.output
    assert "[WARN] pytest collect: no generated pytest files found" in result.output
    assert "fail=0" in result.output


def test_doctor_accepts_single_aitest_yaml_config(tmp_path):
    target = tmp_path / "project"
    (target / "aitest_config").mkdir(parents=True)
    (target / "aitest_config" / "aitest.yaml").write_text(
        """workspace:
  paths:
    generated_dir: test_workspace/generated
    profile_dir: test_workspace/targets
    reports_dir: test_workspace/reports
codegen:
  module_types:
    standard_http:
      description: standard HTTP module
""",
        encoding="utf-8",
    )
    for path in (
        "test_workspace/targets",
        "test_workspace/suites",
        "test_workspace/generated",
        "test_workspace/results",
    ):
        (target / path).mkdir(parents=True)

    result = CliRunner().invoke(main, ["doctor", "--workspace", str(target)])

    assert result.exit_code == 0, result.output
    assert "[OK] workspace layout" in result.output
    assert "[OK] project config" in result.output
    assert "fail=0" in result.output


def test_doctor_checks_case_suite_profiles(tmp_path):
    target = tmp_path / "project"
    runner = CliRunner()
    init_result = runner.invoke(main, ["init", "--target", str(target)])
    assert init_result.exit_code == 0

    target_dir = target / "test_workspace" / "targets" / "demo_target"
    profile_dir = target_dir / "profiles"
    profile_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "target.yaml").write_text(
        """target: demo_target
defaults:
  profile_dir: test_workspace/targets/demo_target/profiles
  generated_dir: test_workspace/generated/demo_target
  reports_dir: test_workspace/reports/demo_target
""",
        encoding="utf-8",
    )
    (profile_dir / "profile_demo.md").write_text(
        """```yaml
module_type: standard_http
```
""",
        encoding="utf-8",
    )
    suite_dir = target / "test_workspace" / "suites" / "demo_target" / "demo_smoke"
    suite_dir.mkdir(parents=True, exist_ok=True)
    (suite_dir / "suite.yaml").write_text(
        """target: demo_target
module: demo
suite: demo_smoke
case_files:
  - smoke.md
profile: profile_demo_smoke_suite.md
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
    (suite_dir / "profile_demo_smoke_suite.md").write_text(
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

    assert result.exit_code == 1, result.output
    assert "[OK] case suites: 1 suite(s) valid" in result.output
    assert "[FAIL] generated freshness" in result.output


def test_doctor_checks_target_registry(tmp_path):
    target = tmp_path / "project"
    runner = CliRunner()
    init_result = runner.invoke(main, ["init", "--target", str(target)])
    assert init_result.exit_code == 0

    target_dir = target / "test_workspace" / "targets" / "demo_target"
    (target_dir / "modules").mkdir(parents=True, exist_ok=True)
    (target_dir / "fixtures").mkdir(parents=True, exist_ok=True)
    (target_dir / "profiles").mkdir(parents=True, exist_ok=True)
    (target_dir / "target.yaml").write_text(
        """target: demo_target
defaults:
  module_dir: test_workspace/targets/demo_target/modules
  fixture_dir: test_workspace/targets/demo_target/fixtures
  profile_dir: test_workspace/targets/demo_target/profiles
  suite_dir: test_workspace/suites/demo_target
  generated_dir: test_workspace/generated/demo_target
  reports_dir: test_workspace/reports/demo_target
""",
        encoding="utf-8",
    )
    (target_dir / "fixtures" / "demo.py").write_text(
        "def setup_demo():\n    return object()\n",
        encoding="utf-8",
    )
    (target_dir / "profiles" / "profile_demo.md").write_text(
        "```yaml\nmodule_type: multi_endpoint\n```\n",
        encoding="utf-8",
    )
    (target_dir / "modules" / "demo.yaml").write_text(
        """target: demo_target
module: demo
module_type: standard_http
fixture:
  file: demo.py
  default_fixture: setup_demo
profile:
  file: profile_demo.md
registered_suites:
  - suite: demo_smoke
    manifest: test_workspace/suites/demo_target/demo_smoke/suite.yaml
    status: active
""",
        encoding="utf-8",
    )

    suite_dir = target / "test_workspace" / "suites" / "demo_target" / "demo_smoke"
    suite_dir.mkdir(parents=True, exist_ok=True)
    (suite_dir / "business.md").write_text("# business\n", encoding="utf-8")
    (suite_dir / "profile_demo_smoke_suite.md").write_text(
        """```yaml
profile_scope: case_suite
parent_module: demo
suite: demo_smoke
case_flows: {}
```
""",
        encoding="utf-8",
    )
    (suite_dir / "suite.yaml").write_text(
        """target: demo_target
module: demo
suite: demo_smoke
case_files:
  - business.md
profile: profile_demo_smoke_suite.md
""",
        encoding="utf-8",
    )

    result = runner.invoke(main, ["doctor", "--workspace", str(target)])

    assert result.exit_code == 1, result.output
    assert "[OK] target registry: 1 target(s), 1 module(s), 1 registered suite(s) valid" in result.output
    assert "[FAIL] generated freshness" in result.output
