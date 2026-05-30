from aitest_kit.report.renderer import render_markdown


def test_render_markdown_separates_precondition_and_scaffold_failures():
    result = {
        "run_id": "run",
        "status": "COMPLETED",
        "timestamp": "2026-05-27T00:00:00+08:00",
        "duration_seconds": 1.0,
        "command": "aitest run --suite-file test_workspace/suites/demo_target/demo_suite/suite.yaml",
        "codegen_check": {"status": "passed"},
        "manual_policy": "excluded",
        "summary": {
            "passed": 0,
            "failed": 1,
            "error": 1,
            "pytest_skipped": 0,
            "auto_collected": 2,
            "manual_total": 0,
            "manual_executed": 0,
            "manual_not_run": 0,
            "codegen_skipped": 0,
        },
        "modules": {},
        "cases": [
            {
                "tc_id": "TC-DEMO-001",
                "module": "demo",
                "nodeid": "test_demo.py::TestDemo::test_1",
                "failure": {
                    "classification": "PRECONDITION_MISSING",
                    "message": "profile variable environment missing: DEMO_TOKEN",
                    "missing_env": ["DEMO_TOKEN"],
                },
            },
            {
                "tc_id": "TC-DEMO-002",
                "module": "demo",
                "nodeid": "test_demo.py::TestDemo::test_2",
                "failure": {
                    "classification": "TEST_SCAFFOLD_ERROR",
                    "message": "fixture failed",
                },
            },
        ],
        "codegen_skipped_cases": [],
    }

    text = render_markdown(result)

    assert "### PRECONDITION_MISSING（1 条）" in text
    assert "### TEST_SCAFFOLD_ERROR（1 条）" in text
    assert "### 运行前置条件缺失" in text
    assert "TC-DEMO-001：缺失 env：DEMO_TOKEN" in text
    assert "### 需要修 scaffold / fixture / helper" in text
    assert "TC-DEMO-002：fixture failed" in text


def test_render_markdown_includes_suite_scope():
    result = {
        "run_id": "run",
        "status": "COMPLETED",
        "timestamp": "2026-05-27T00:00:00+08:00",
        "duration_seconds": 1.0,
        "command": "aitest run --suite-file external_suites/demo/suite.yaml",
        "target": "sub2api",
        "module": "gateway_api",
        "suite": "quota_billing_v2",
        "suite_file": "external_suites/demo/suite.yaml",
        "codegen_check": {"status": "passed"},
        "manual_policy": "excluded",
        "summary": {
            "passed": 1,
            "failed": 0,
            "error": 0,
            "pytest_skipped": 0,
            "auto_collected": 1,
            "manual_total": 0,
            "manual_executed": 0,
            "manual_not_run": 0,
            "codegen_skipped": 0,
        },
        "modules": {},
        "cases": [],
        "codegen_skipped_cases": [],
    }

    text = render_markdown(result)

    assert "- **Target**：sub2api" in text
    assert "- **Module**：gateway_api" in text
    assert "- **Suite**：quota_billing_v2" in text
    assert "- **Suite 文件**：external_suites/demo/suite.yaml" in text


def test_render_markdown_lists_manual_cases():
    result = {
        "run_id": "run",
        "status": "COMPLETED",
        "timestamp": "2026-05-27T00:00:00+08:00",
        "duration_seconds": 1.0,
        "command": "aitest run --suite-file external_suites/demo/suite.yaml",
        "codegen_check": {"status": "passed"},
        "manual_policy": "excluded",
        "summary": {
            "passed": 0,
            "failed": 0,
            "error": 0,
            "pytest_skipped": 0,
            "auto_collected": 0,
            "manual_total": 1,
            "manual_executed": 0,
            "manual_not_run": 1,
            "codegen_skipped": 0,
        },
        "modules": {},
        "cases": [],
        "manual_cases": [
            {
                "tc_id": "TC-DEMO-001",
                "module": "demo",
                "suite": "smoke",
                "title": "人工检查监控",
            }
        ],
        "codegen_skipped_cases": [],
    }

    text = render_markdown(result)

    assert "## Manual 用例" in text
    assert "TC-DEMO-001：人工检查监控（demo/smoke）" in text
