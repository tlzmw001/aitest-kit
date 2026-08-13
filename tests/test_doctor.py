from __future__ import annotations

from click.testing import CliRunner

from aitest_kit.cli import main
from aitest_kit.doctor import _scan_env_vars


def _write_canonical_module(target, *, module_type: str = "standard_http"):
    target_dir = target / "test_workspace" / "targets" / "demo_target"
    module_dir = target_dir / "modules" / "demo"
    module_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "target.yaml").write_text(
        """target: demo_target
defaults:
  module_dir: test_workspace/targets/demo_target/modules
  suite_dir: test_workspace/suites/demo_target
  generated_dir: test_workspace/generated/demo_target
  reports_dir: test_workspace/reports/demo_target
""",
        encoding="utf-8",
    )
    (module_dir / "__init__.py").write_text("", encoding="utf-8")
    (module_dir / "module.yaml").write_text(
        f"""target: demo_target
module: demo
module_type: {module_type}
registered_suites:
  - suite: demo_smoke
    manifest: test_workspace/suites/demo_target/demo_smoke/suite.yaml
    status: active
""",
        encoding="utf-8",
    )
    (module_dir / "profile.md").write_text("```yaml\n{}\n```\n", encoding="utf-8")
    (module_dir / "harness.py").write_text(
        """class DemoHarness:
    def health(self):
        return {"status": "ok"}
""",
        encoding="utf-8",
    )
    (module_dir / "fixture.py").write_text(
        """import pytest

from .harness import DemoHarness


@pytest.fixture
def setup_demo() -> DemoHarness:
    return DemoHarness()
""",
        encoding="utf-8",
    )
    return module_dir


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

    _write_canonical_module(target)
    suite_dir = target / "test_workspace" / "suites" / "demo_target" / "demo_smoke"
    suite_dir.mkdir(parents=True, exist_ok=True)
    (suite_dir / "suite.yaml").write_text(
        """target: demo_target
module: demo
suite: demo_smoke
case_files:
  - smoke.md
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
    steps:
      - call: harness.health
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

    _write_canonical_module(target)

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
""",
        encoding="utf-8",
    )

    result = runner.invoke(main, ["doctor", "--workspace", str(target)])

    assert result.exit_code == 1, result.output
    assert (
        "[WARN] target registry: demo_target/demo: missing recommended knowledge_refs.l1"
        in result.output
    )
    assert "[FAIL] generated freshness" in result.output


def test_doctor_rejects_broken_harness_contract(tmp_path):
    target = tmp_path / "project"
    runner = CliRunner()
    assert runner.invoke(main, ["init", "--target", str(target)]).exit_code == 0
    module_dir = _write_canonical_module(target)
    (module_dir / "harness.py").write_text("class WrongHarness:\n    pass\n", encoding="utf-8")
    (module_dir / "fixture.py").write_text(
        """import pytest


@pytest.fixture
def setup_demo():
    return lambda: object()


@pytest.fixture
def extra_fixture():
    return object()
""",
        encoding="utf-8",
    )

    result = runner.invoke(main, ["doctor", "--workspace", str(target)])

    assert result.exit_code == 1, result.output
    assert "setup_demo return annotation must reference DemoHarness" in result.output
    assert "fixture.py exposes additional public pytest fixtures: extra_fixture" in result.output
    assert "harness.py must define DemoHarness" in result.output


def test_scan_env_vars_discovers_harness_runtime_requirements(tmp_path):
    module_dir = tmp_path / "test_workspace" / "targets" / "demo" / "modules" / "gateway"
    module_dir.mkdir(parents=True)
    (module_dir / "harness.py").write_text(
        '''from aitest_kit.runtime_variables import require_env, require_envs


class GatewayHarness:
    def api_url(self):
        return require_env("GATEWAY_BASE_URL")

    def credentials(self):
        return require_envs(
            [
                "GATEWAY_USER",
                "GATEWAY_PASSWORD",
            ]
        )
''',
        encoding="utf-8",
    )

    assert _scan_env_vars(tmp_path / "test_workspace" / "targets") == {
        "GATEWAY_BASE_URL",
        "GATEWAY_USER",
        "GATEWAY_PASSWORD",
    }
