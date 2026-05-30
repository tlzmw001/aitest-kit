from pathlib import Path

from aitest_kit.report.collector import collect_result


def test_collect_result_joins_junit_without_nodeid_and_counts_manual_and_codegen_skipped(tmp_path):
    generated = tmp_path / "test_demo_business.py"
    generated.write_text(
        '''
import pytest


class TestDemoBusiness:
    def test_tc_demo_001(self):
        """TC-DEMO-001：normal"""
        __tc_meta__ = {
            "tc_id": "TC-DEMO-001",
            "module": "demo",
            "category": "business",
            "source": "test_workspace/suites/demo_target/demo_suite/business.md",
            "title": "normal",
            "priority": "P1",
            "markers": [],
        }

    @pytest.mark.manual
    def test_tc_demo_002(self):
        """TC-DEMO-002：manual"""
        __tc_meta__ = {
            "tc_id": "TC-DEMO-002",
            "module": "demo",
            "category": "business",
            "source": "test_workspace/suites/demo_target/demo_suite/business.md",
            "title": "manual",
            "priority": "P2",
            "markers": ["manual"],
        }


__codegen_skipped__ = [
    {
        "tc_id": "TC-DEMO-003",
        "module": "demo",
        "category": "business",
        "source": "test_workspace/suites/demo_target/demo_suite/business.md",
        "title": "skipped",
        "priority": "P2",
        "reason": "[!可行性存疑: demo]",
    }
]
''',
        encoding="utf-8",
    )
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '''<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" tests="1" failures="0" errors="0" skipped="0">
  <testcase classname="test_demo_business.TestDemoBusiness" name="test_tc_demo_001" time="0.12" />
</testsuite>
''',
        encoding="utf-8",
    )

    result = collect_result(
        junit_path=junit,
        generated_files=[generated],
        run_id="run",
        command="aitest run --suite-file test_workspace/suites/demo_target/demo_suite/suite.yaml",
        manual_policy="excluded",
        codegen_check={"status": "passed", "command": "check", "message": ""},
    )

    assert result["cases"][0]["tc_id"] == "TC-DEMO-001"
    assert result["cases"][0]["meta_source"] == "tc_meta"
    assert result["cases"][0]["nodeid"] == f"{generated.as_posix()}::TestDemoBusiness::test_tc_demo_001"
    assert result["summary"]["manual_total"] == 1
    assert result["summary"]["manual_executed"] == 0
    assert result["summary"]["manual_not_run"] == 1
    assert result["summary"]["codegen_skipped"] == 1
    assert result["modules"]["demo"]["business"]["manual_total"] == 1
    assert result["modules"]["demo"]["business"]["manual_not_run"] == 1
    assert result["manual_cases"][0]["tc_id"] == "TC-DEMO-002"
    assert result["manual_cases"][0]["title"] == "manual"
    assert result["codegen_skipped_cases"][0]["tc_id"] == "TC-DEMO-003"


def test_collect_result_preserves_run_scope_metadata(tmp_path):
    result = collect_result(
        junit_path=None,
        generated_files=[],
        run_id="run",
        command="aitest run --suite-file external_suites/demo/suite.yaml",
        codegen_check={"status": "passed", "command": "check", "message": ""},
        run_scope={
            "type": "suite_file",
            "target": "sub2api",
            "module": "gateway_api",
            "suite": "quota_billing_v2",
            "suite_file": "external_suites/demo/suite.yaml",
            "suite_dir": "external_suites/demo",
            "case_files": ["external_suites/demo/business.md"],
        },
    )

    assert result["target"] == "sub2api"
    assert result["module"] == "gateway_api"
    assert result["suite"] == "quota_billing_v2"
    assert result["suite_file"] == "external_suites/demo/suite.yaml"
    assert result["suite_dir"] == "external_suites/demo"
    assert result["case_files"] == ["external_suites/demo/business.md"]
    assert result["run_scope"]["type"] == "suite_file"


def test_collect_result_classifies_failure(tmp_path):
    generated = tmp_path / "test_demo_business.py"
    generated.write_text(
        '''
class TestDemoBusiness:
    def test_tc_demo_001(self):
        """TC-DEMO-001：normal"""
        __tc_meta__ = {
            "tc_id": "TC-DEMO-001",
            "module": "demo",
            "category": "business",
            "source": "test_workspace/suites/demo_target/demo_suite/business.md",
            "title": "normal",
            "priority": "P1",
            "markers": [],
        }


__codegen_skipped__ = []
''',
        encoding="utf-8",
    )
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '''<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" tests="1" failures="1" errors="0" skipped="0">
  <testcase classname="test_demo_business.TestDemoBusiness" name="test_tc_demo_001" time="0.12">
    <failure type="AssertionError" message="AssertionError: assert 1 == 2">File "/tmp/test_demo_business.py", line 5, in test_tc_demo_001
AssertionError: assert 1 == 2</failure>
  </testcase>
</testsuite>
''',
        encoding="utf-8",
    )

    result = collect_result(
        junit_path=junit,
        generated_files=[generated],
        run_id="run",
        command="aitest run --suite-file test_workspace/suites/demo_target/demo_suite/suite.yaml",
        codegen_check={"status": "passed", "command": "check", "message": ""},
    )

    failure = result["cases"][0]["failure"]
    assert failure["classification"] == "ASSERTION_FAILURE"
    assert failure["traceback_summary"] == "test_demo_business.py:5: AssertionError"


def test_collect_result_classifies_profile_variable_errors_as_preconditions(tmp_path):
    generated = tmp_path / "test_demo_business.py"
    generated.write_text(
        '''
class TestDemoBusiness:
    def test_tc_demo_001(self):
        """TC-DEMO-001：normal"""
        __tc_meta__ = {
            "tc_id": "TC-DEMO-001",
            "module": "demo",
            "category": "business",
            "source": "test_workspace/suites/demo_target/demo_suite/business.md",
            "title": "normal",
            "priority": "P1",
            "markers": [],
        }


__codegen_skipped__ = []
''',
        encoding="utf-8",
    )
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '''<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" tests="1" failures="0" errors="1" skipped="0">
  <testcase classname="test_demo_business.TestDemoBusiness" name="test_tc_demo_001" time="0.12">
    <error type="aitest_kit.runtime_variables.ProfileVariableError" message="aitest_kit.runtime_variables.ProfileVariableError: profile variable environment missing: SUB2API_ADMIN_TOKEN, SUB2API_BASE_URL">File "/tmp/test_demo_business.py", line 5, in test_tc_demo_001
aitest_kit.runtime_variables.ProfileVariableError: profile variable environment missing: SUB2API_ADMIN_TOKEN, SUB2API_BASE_URL</error>
  </testcase>
</testsuite>
''',
        encoding="utf-8",
    )

    result = collect_result(
        junit_path=junit,
        generated_files=[generated],
        run_id="run",
        command="aitest run --suite-file test_workspace/suites/demo_target/demo_suite/suite.yaml",
        codegen_check={"status": "passed", "command": "check", "message": ""},
    )

    failure = result["cases"][0]["failure"]
    assert failure["classification"] == "PRECONDITION_MISSING"
    assert failure["failure_type"] == "PRECONDITION_MISSING"
    assert failure["blocker_type"] == "precondition_unmet"
    assert failure["exception_type"] == "ProfileVariableError"
    assert failure["missing_env"] == ["SUB2API_ADMIN_TOKEN", "SUB2API_BASE_URL"]


def test_collect_result_classifies_precondition_missing_as_preconditions(tmp_path):
    generated = tmp_path / "test_demo_business.py"
    generated.write_text(
        '''
class TestDemoBusiness:
    def test_tc_demo_001(self):
        """TC-DEMO-001：normal"""
        __tc_meta__ = {
            "tc_id": "TC-DEMO-001",
            "module": "demo",
            "category": "business",
            "source": "test_workspace/suites/demo_target/demo_suite/business.md",
            "title": "normal",
            "priority": "P1",
            "markers": [],
        }


__codegen_skipped__ = []
''',
        encoding="utf-8",
    )
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '''<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" tests="1" failures="0" errors="1" skipped="0">
  <testcase classname="test_demo_business.TestDemoBusiness" name="test_tc_demo_001" time="0.12">
    <error type="aitest_kit.runtime_variables.PreconditionMissing" message="aitest_kit.runtime_variables.PreconditionMissing: profile variable environment missing: SUB2API_ADMIN_TOKEN">File "/tmp/test_demo_business.py", line 5, in test_tc_demo_001
aitest_kit.runtime_variables.PreconditionMissing: profile variable environment missing: SUB2API_ADMIN_TOKEN</error>
  </testcase>
</testsuite>
''',
        encoding="utf-8",
    )

    result = collect_result(
        junit_path=junit,
        generated_files=[generated],
        run_id="run",
        command="aitest run --suite-file test_workspace/suites/demo_target/demo_suite/suite.yaml",
        codegen_check={"status": "passed", "command": "check", "message": ""},
    )

    failure = result["cases"][0]["failure"]
    assert failure["classification"] == "PRECONDITION_MISSING"
    assert failure["failure_type"] == "PRECONDITION_MISSING"
    assert failure["blocker_type"] == "precondition_unmet"
    assert failure["exception_type"] == "PreconditionMissing"
    assert failure["missing_env"] == ["SUB2API_ADMIN_TOKEN"]
