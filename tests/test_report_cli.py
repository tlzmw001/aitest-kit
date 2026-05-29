from __future__ import annotations

import json
import re
import textwrap

import pytest

from aitest_kit.report.cli import _create_run_dir, _run_command_impl


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


def test_run_loads_aitest_env_file_into_pytest_subprocess(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env_file = tmp_path / "local.env"
    env_file.write_text("DEMO_TOKEN=from-env-file\n", encoding="utf-8")
    monkeypatch.setenv("AITEST_ENV_FILE", str(env_file))
    monkeypatch.delenv("DEMO_TOKEN", raising=False)
    generated = tmp_path / "test_workspace" / "tests" / "generated"
    generated.mkdir(parents=True)
    (generated / "test_demo_business.py").write_text(
        textwrap.dedent(
            '''
            import os


            class TestDemoBusiness:
                def test_tc_demo_001(self):
                    __tc_meta__ = {
                        "tc_id": "TC-DEMO-001",
                        "module": "demo",
                        "category": "business",
                        "source": "test_workspace/cases/demo/business.md",
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
        _run_command_impl(False, True, ("demo",))

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

    with pytest.raises(SystemExit) as exc_info:
        _run_command_impl(False, True, ())

    assert exc_info.value.code == 10
    result_path = tmp_path / "test_workspace" / "reports" / "latest" / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["status"] == "BLOCKED_RUN"
    assert result["blocked_reason"] == "env_file"
    assert result["environment"]["env_file"] == str(missing)
    assert result["environment"]["env_file_configured"] is True
    assert result["environment"]["env_file_loaded"] is False
    assert "env file not found" in result["environment"]["env_file_error"]


def test_run_cases_executes_suite_generated_file_and_reports_dynamic_category(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AITEST_ENV_FILE", raising=False)
    suite_dir = tmp_path / "test_workspace" / "casesuites" / "quota_billing_v2"
    suite_dir.mkdir(parents=True)
    (suite_dir / "aitest_suite.yaml").write_text(
        """module: gateway_api
suite: quota_billing_v2
case_files:
  - quota_billing_business.md
profile: codegen_profile_quota_billing_v2_suite.md
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
    generated = tmp_path / "test_workspace" / "tests" / "generated"
    generated.mkdir(parents=True)
    (generated / "test_gateway_api_quota_billing_v2_quota_billing_business.py").write_text(
        textwrap.dedent(
            '''
            class TestGatewayApiQuotaBillingV2QuotaBillingBusiness:
                def test_tc_gw_041(self):
                    __tc_meta__ = {
                        "tc_id": "TC-GW-041",
                        "module": "gateway_api",
                        "category": "quota_billing_business",
                        "source": "test_workspace/casesuites/quota_billing_v2/quota_billing_business.md",
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
        _run_command_impl(False, True, (), cases_path=str(suite_dir))

    assert exc_info.value.code == 0
    result_path = tmp_path / "test_workspace" / "reports" / "latest" / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["summary"]["passed"] == 1
    assert result["cases"][0]["suite"] == "quota_billing_v2"
    report = (tmp_path / "test_workspace" / "reports" / "latest" / "report.md").read_text(encoding="utf-8")
    assert "quota_billing_business" in report
