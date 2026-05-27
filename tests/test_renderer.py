from aitest_kit.report.renderer import render_markdown


def test_render_markdown_separates_precondition_and_scaffold_failures():
    result = {
        "run_id": "run",
        "status": "COMPLETED",
        "timestamp": "2026-05-27T00:00:00+08:00",
        "duration_seconds": 1.0,
        "command": "aitest run demo",
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
