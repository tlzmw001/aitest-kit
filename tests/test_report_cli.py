from __future__ import annotations

import json
import re
import subprocess
import textwrap

import pytest

from aitest_kit.report.codegen_check import run_codegen_check
from aitest_kit.report.cli import _create_run_dir, _report_command_impl, _run_command_impl


def test_create_run_dir_uses_unique_filesystem_directory(tmp_path):
    first_id, first_dir = _create_run_dir(tmp_path)
    second_id, second_dir = _create_run_dir(tmp_path)

    pattern = re.compile(r"^\d{8}-\d{6}-\d{6}-[0-9a-f]{6}$")
    assert pattern.match(first_id)
    assert pattern.match(second_id)
    assert first_id != second_id
    assert first_dir.exists()
    assert second_dir.exists()
    assert first_dir != second_dir


def test_codegen_check_uses_suite_file_option_for_suite_manifest(monkeypatch):
    captured: dict[str, list[str]] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr("aitest_kit.report.codegen_check.subprocess.run", fake_run)

    result = run_codegen_check(
        False,
        suite_file="test_workspace/suites/demo/suite.yaml",
    )

    assert result["status"] == "passed"
    assert "--suite-file" in captured["cmd"]
    assert "--cases" not in captured["cmd"]
    assert captured["cmd"][-1] == "--check"


def test_run_loads_aitest_env_file_into_pytest_subprocess(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env_file = tmp_path / "local.env"
    env_file.write_text("DEMO_TOKEN=from-env-file\n", encoding="utf-8")
    monkeypatch.setenv("AITEST_ENV_FILE", str(env_file))
    monkeypatch.delenv("DEMO_TOKEN", raising=False)
    suite_dir = tmp_path / "test_workspace" / "suites" / "demo_target" / "demo_smoke"
    suite_dir.mkdir(parents=True)
    suite_file = suite_dir / "suite.yaml"
    suite_file.write_text(
        """target: demo_target
module: demo
suite: demo_smoke
case_files:
  - business.md
profile: profile_demo_smoke_suite.md
""",
        encoding="utf-8",
    )
    (suite_dir / "business.md").write_text("# demo\n", encoding="utf-8")
    generated = tmp_path / "test_workspace" / "generated"
    generated.mkdir(parents=True)
    (generated / "test_demo_demo_smoke_business.py").write_text(
        textwrap.dedent(
            '''
            import os


            class TestDemoBusiness:
                def test_tc_demo_001(self):
                    __tc_meta__ = {
                        "tc_id": "TC-DEMO-001",
                        "module": "demo",
                            "category": "demo_smoke_business",
                            "source": "test_workspace/suites/demo_target/demo_smoke/business.md",
                        "title": "env file",
                        "priority": "P1",
                        "markers": [],
                    }
                    assert os.environ["DEMO_TOKEN"] == "from-env-file"


            __codegen_skipped__ = []
            '''
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        _run_command_impl(False, True, (), suite_file=str(suite_file))

    assert exc_info.value.code == 0
    latest = tmp_path / "test_workspace" / "reports" / "latest" / "result.json"
    result = json.loads(latest.read_text(encoding="utf-8"))
    assert result["summary"]["passed"] == 1
    assert result["environment"] == {
        "env_file": str(env_file),
        "env_file_configured": True,
        "env_file_loaded": True,
        "env_file_keys": ["DEMO_TOKEN"],
    }
    assert "from-env-file" not in latest.read_text(encoding="utf-8")


def test_run_blocks_when_configured_env_file_is_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    missing = tmp_path / "missing.env"
    monkeypatch.setenv("AITEST_ENV_FILE", str(missing))
    suite_dir = tmp_path / "test_workspace" / "suites" / "demo_target" / "demo_smoke"
    suite_dir.mkdir(parents=True)
    suite_file = suite_dir / "suite.yaml"
    suite_file.write_text(
        """target: demo_target
module: demo
suite: demo_smoke
case_files:
  - business.md
profile: profile_demo_smoke_suite.md
""",
        encoding="utf-8",
    )
    (suite_dir / "business.md").write_text("# demo\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        _run_command_impl(False, True, (), suite_file=str(suite_file))

    assert exc_info.value.code == 10
    result_path = tmp_path / "test_workspace" / "reports" / "latest" / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["status"] == "BLOCKED_RUN"
    assert result["blocked_reason"] == "env_file"
    assert result["environment"]["env_file"] == str(missing)
    assert result["environment"]["env_file_configured"] is True
    assert result["environment"]["env_file_loaded"] is False
    assert "env file not found" in result["environment"]["env_file_error"]


def test_run_suite_file_executes_generated_file_and_reports_dynamic_category(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AITEST_ENV_FILE", raising=False)
    suite_dir = tmp_path / "test_workspace" / "suites" / "sub2api" / "quota_billing_v2"
    suite_dir.mkdir(parents=True)
    suite_file = suite_dir / "suite.yaml"
    suite_file.write_text(
        """target: sub2api
module: gateway_api
suite: quota_billing_v2
case_files:
  - quota_billing_business.md
profile: profile_quota_billing_v2_suite.md
""",
        encoding="utf-8",
    )
    (suite_dir / "quota_billing_business.md").write_text(
        """# quota billing

### TC-GW-041：suite case
- **优先级**：P0
- **断言**：`response.status == "ok"`
""",
        encoding="utf-8",
    )
    generated = tmp_path / "test_workspace" / "generated"
    generated.mkdir(parents=True)
    (generated / "test_gateway_api_quota_billing_v2_quota_billing_business.py").write_text(
        textwrap.dedent(
            '''
            class TestGatewayApiQuotaBillingV2QuotaBillingBusiness:
                def test_tc_gw_041(self):
                    __tc_meta__ = {
                        "tc_id": "TC-GW-041",
                        "module": "gateway_api",
                        "suite": "quota_billing_v2",
                        "category": "quota_billing_business",
                        "source": "test_workspace/suites/sub2api/quota_billing_v2/quota_billing_business.md",
                        "title": "suite case",
                        "priority": "P0",
                        "markers": [],
                    }
                    assert True


            __codegen_skipped__ = []
            '''
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        _run_command_impl(False, True, (), suite_file=str(suite_file))

    assert exc_info.value.code == 0
    result_path = tmp_path / "test_workspace" / "reports" / "latest" / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["summary"]["passed"] == 1
    assert result["module"] == "gateway_api"
    assert result["suite"] == "quota_billing_v2"
    assert result["suite_file"].endswith("suite.yaml")
    assert result["run_scope"]["type"] == "suite_file"
    assert result["cases"][0]["suite"] == "quota_billing_v2"
    report = (tmp_path / "test_workspace" / "reports" / "latest" / "report.md").read_text(encoding="utf-8")
    assert "- **Suite**：quota_billing_v2" in report
    assert "quota_billing_business" in report


def test_run_suite_file_and_task_execute_suite_generated_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AITEST_ENV_FILE", raising=False)
    suite_dir = tmp_path / "external_suites" / "quota_billing_v2"
    suite_dir.mkdir(parents=True)
    suite_file = suite_dir / "suite.yaml"
    suite_file.write_text(
        """target: sub2api
module: gateway_api
suite: quota_billing_v2
case_files:
  - quota_billing_business.md
profile: profile_quota_billing_v2_suite.md
""",
        encoding="utf-8",
    )
    (suite_dir / "quota_billing_business.md").write_text(
        """# quota billing

### TC-GW-041：suite case
- **优先级**：P0
- **断言**：`response.status == "ok"`
""",
        encoding="utf-8",
    )
    generated = tmp_path / "test_workspace" / "generated"
    generated.mkdir(parents=True)
    (generated / "test_gateway_api_quota_billing_v2_quota_billing_business.py").write_text(
        textwrap.dedent(
            '''
            class TestGatewayApiQuotaBillingV2QuotaBillingBusiness:
                def test_tc_gw_041(self):
                    __tc_meta__ = {
                        "tc_id": "TC-GW-041",
                        "module": "gateway_api",
                        "suite": "quota_billing_v2",
                        "category": "quota_billing_business",
                        "source": "external_suites/quota_billing_v2/quota_billing_business.md",
                        "title": "suite case",
                        "priority": "P0",
                        "markers": [],
                    }
                    assert True


            __codegen_skipped__ = []
            '''
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        _run_command_impl(False, True, (), suite_file=str(suite_file))

    assert exc_info.value.code == 0
    result_path = tmp_path / "test_workspace" / "reports" / "latest" / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["summary"]["passed"] == 1
    assert result["command"].startswith("aitest run --suite-file ")
    assert result["target"] == "sub2api"
    assert result["module"] == "gateway_api"
    assert result["suite"] == "quota_billing_v2"
    assert result["suite_file"] == str(suite_file)
    assert result["suite_dir"] == str(suite_dir)
    assert result["case_files"] == ["external_suites/quota_billing_v2/quota_billing_business.md"]
    assert result["run_scope"]["type"] == "suite_file"

    task_dir = tmp_path / "test_workspace" / "tasks"
    task_dir.mkdir(parents=True)
    task_file = task_dir / "release_regression.yaml"
    task_file.write_text(
        f"""task: release_regression
units:
  - target: sub2api
    module: gateway_api
    suite: quota_billing_v2
    suite_file: {suite_file}
    case_ids:
      - TC-GW-041
""",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as task_exit:
        _run_command_impl(False, True, (), task_file=str(task_file))

    assert task_exit.value.code == 0
    task_result_path = tmp_path / "test_workspace" / "reports" / "tasks" / "release_regression" / "latest" / "result.json"
    task_result = json.loads(task_result_path.read_text(encoding="utf-8"))
    assert task_result["summary"]["passed"] == 1
    assert task_result["task_file"] == str(task_file)
    assert task_result["run_scope"]["type"] == "task"
    assert task_result["task"]["name"] == "release_regression"
    assert task_result["task"]["units"][0]["target"] == "sub2api"


def test_run_suite_file_uses_target_generated_and_reports_dirs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AITEST_ENV_FILE", raising=False)
    target_dir = tmp_path / "test_workspace" / "targets" / "sub2api"
    profile_dir = target_dir / "profiles"
    profile_dir.mkdir(parents=True)
    (target_dir / "target.yaml").write_text(
        """target: sub2api
defaults:
  profile_dir: test_workspace/targets/sub2api/profiles
  generated_dir: test_workspace/generated/sub2api
  reports_dir: test_workspace/reports/sub2api
""",
        encoding="utf-8",
    )
    (profile_dir / "profile_gateway_api.md").write_text(
        """```yaml
module_type: multi_endpoint
case_flows:
  TC-GW-041:
    fixture: setup_gateway_api
    steps:
      - assert: 'assert True'
```
""",
        encoding="utf-8",
    )
    suite_dir = tmp_path / "external_suites" / "quota_billing_v2"
    suite_dir.mkdir(parents=True)
    suite_file = suite_dir / "suite.yaml"
    suite_file.write_text(
        """target: sub2api
module: gateway_api
suite: quota_billing_v2
case_files:
  - quota_billing_business.md
""",
        encoding="utf-8",
    )
    (suite_dir / "quota_billing_business.md").write_text(
        """# quota billing

### TC-GW-041：suite case
- **优先级**：P0
- **断言**：`response.status == "ok"`
""",
        encoding="utf-8",
    )
    generated = tmp_path / "test_workspace" / "generated" / "sub2api"
    generated.mkdir(parents=True)
    (generated / "test_gateway_api_quota_billing_v2_quota_billing_business.py").write_text(
        textwrap.dedent(
            '''
            class TestGatewayApiQuotaBillingV2QuotaBillingBusiness:
                def test_tc_gw_041(self):
                    __tc_meta__ = {
                        "tc_id": "TC-GW-041",
                        "module": "gateway_api",
                        "suite": "quota_billing_v2",
                        "category": "quota_billing_business",
                        "source": "external_suites/quota_billing_v2/quota_billing_business.md",
                        "title": "suite case",
                        "priority": "P0",
                        "markers": [],
                    }
                    assert True


            __codegen_skipped__ = []
            '''
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        _run_command_impl(False, True, (), suite_file=str(suite_file))

    assert exc_info.value.code == 0
    result_path = tmp_path / "test_workspace" / "reports" / "sub2api" / "latest" / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["summary"]["passed"] == 1
    assert result["target"] == "sub2api"
    assert result["module"] == "gateway_api"
    assert result["suite"] == "quota_billing_v2"
    assert result["suite_file"] == str(suite_file)

    report_path = tmp_path / "test_workspace" / "reports" / "sub2api" / "latest" / "report.md"
    report_path.write_text("stale\n", encoding="utf-8")
    _report_command_impl(None, suite_file=str(suite_file))
    assert "# 测试执行报告" in report_path.read_text(encoding="utf-8")
    assert "stale" not in report_path.read_text(encoding="utf-8")


def test_run_task_loads_env_files_and_filters_case_ids(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AITEST_ENV_FILE", raising=False)
    suite_dir = tmp_path / "external_suites" / "task_env_smoke"
    suite_dir.mkdir(parents=True)
    suite_file = suite_dir / "suite.yaml"
    suite_file.write_text(
        """target: sub2api
module: gateway_api
suite: task_env_smoke
case_files:
  - business.md
profile: profile_task_env_smoke_suite.md
""",
        encoding="utf-8",
    )
    (suite_dir / "business.md").write_text(
        """# task env smoke

### TC-GW-041：selected case
- **优先级**：P0
- **断言**：`response.status == "ok"`

### TC-GW-042：non selected case
- **优先级**：P0
- **断言**：`response.status == "ok"`
""",
        encoding="utf-8",
    )
    generated = tmp_path / "test_workspace" / "generated"
    generated.mkdir(parents=True)
    (generated / "test_gateway_api_task_env_smoke_business.py").write_text(
        textwrap.dedent(
            '''
            import os


            class TestGatewayApiTaskEnvSmokeBusiness:
                def test_tc_gw_041(self):
                    __tc_meta__ = {
                        "tc_id": "TC-GW-041",
                        "module": "gateway_api",
                        "suite": "task_env_smoke",
                        "category": "business",
                        "source": "external_suites/task_env_smoke/business.md",
                        "title": "selected case",
                        "priority": "P0",
                        "markers": [],
                    }
                    assert os.environ["TASK_TOKEN"] == "from-task-env"

                def test_tc_gw_042(self):
                    __tc_meta__ = {
                        "tc_id": "TC-GW-042",
                        "module": "gateway_api",
                        "suite": "task_env_smoke",
                        "category": "business",
                        "source": "external_suites/task_env_smoke/business.md",
                        "title": "non selected case",
                        "priority": "P0",
                        "markers": [],
                    }
                    assert False


            __codegen_skipped__ = []
            '''
        ),
        encoding="utf-8",
    )

    task_dir = tmp_path / "test_workspace" / "tasks"
    task_dir.mkdir(parents=True)
    env_file = task_dir / "task.env"
    env_file.write_text("TASK_TOKEN=from-task-env\n", encoding="utf-8")
    task_file = task_dir / "task_env.yaml"
    task_file.write_text(
        f"""task: task_env
env_files:
  - task.env
defaults:
  include_manual: false
  pytest_args:
    - -q
units:
  - name: selected
    suite_file: {suite_file}
    case_ids:
      - TC-GW-041
""",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as task_exit:
        _run_command_impl(False, True, (), task_file=str(task_file))

    assert task_exit.value.code == 0
    result_path = tmp_path / "test_workspace" / "reports" / "tasks" / "task_env" / "latest" / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["summary"]["passed"] == 1
    assert result["summary"]["failed"] == 0
    assert result["task"]["units"][0]["name"] == "selected"
    assert result["environment"]["env_file"] == str(env_file)
    assert result["environment"]["env_files"] == [str(env_file)]
    assert result["environment"]["env_file_keys"] == ["TASK_TOKEN"]
    assert "from-task-env" not in result_path.read_text(encoding="utf-8")

    report_path = tmp_path / "test_workspace" / "reports" / "tasks" / "task_env" / "latest" / "report.md"
    report_path.write_text("stale\n", encoding="utf-8")
    _report_command_impl(None, task_file=str(task_file))
    assert "# 测试执行报告" in report_path.read_text(encoding="utf-8")
    assert "stale" not in report_path.read_text(encoding="utf-8")
