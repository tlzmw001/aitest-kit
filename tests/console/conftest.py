from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def console_workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    (root / "aitest_config").mkdir(parents=True)
    (root / "aitest_config" / "aitest.yaml").write_text(
        """
workspace:
  paths:
    generated_dir: test_workspace/generated
    reports_dir: test_workspace/reports
""".lstrip(),
        encoding="utf-8",
    )

    module_dir = root / "test_workspace" / "targets" / "demo" / "modules" / "orders"
    suite_dir = root / "test_workspace" / "suites" / "demo" / "orders_smoke"
    task_dir = root / "test_workspace" / "tasks"
    report_dir = root / "test_workspace" / "reports" / "demo" / "orders" / "runs" / "run-1"
    generated_dir = root / "test_workspace" / "generated" / "demo"
    results_dir = root / "test_workspace" / "results"
    for directory in (module_dir, suite_dir, task_dir, report_dir, generated_dir, results_dir):
        directory.mkdir(parents=True, exist_ok=True)

    (root / "test_workspace" / "targets" / "demo" / "target.yaml").write_text(
        "target: demo\n", encoding="utf-8"
    )
    (module_dir / "module.yaml").write_text(
        """
target: demo
module: orders
module_type: multi_endpoint
registered_suites:
  - suite: orders_smoke
    manifest: test_workspace/suites/demo/orders_smoke/suite.yaml
    status: active
""".lstrip(),
        encoding="utf-8",
    )
    (module_dir / "profile.md").write_text("# orders profile\n", encoding="utf-8")
    (module_dir / "fixture.py").write_text("def setup_orders():\n    return None\n", encoding="utf-8")
    (module_dir / "harness.py").write_text("class OrdersHarness:\n    pass\n", encoding="utf-8")

    (suite_dir / "suite.yaml").write_text(
        """
target: demo
module: orders
suite: orders_smoke
case_files:
  - business.md
""".lstrip(),
        encoding="utf-8",
    )
    (suite_dir / "business.md").write_text(
        """
# Orders smoke

### TC-ORD-001：创建订单
- **优先级**：P1
- **断言**：返回成功
""".lstrip(),
        encoding="utf-8",
    )
    (suite_dir / "profile_orders_smoke_suite.md").write_text(
        "# suite profile\n", encoding="utf-8"
    )
    (task_dir / "nightly.env").write_text("TASK_TOKEN=local-token\n", encoding="utf-8")
    (task_dir / "nightly.yaml").write_text(
        """
schema_version: 1
name: nightly
env_files:
  - nightly.env
units:
  - name: orders smoke
    target: demo
    module: orders
    suite: orders_smoke
    suite_file: ../suites/demo/orders_smoke/suite.yaml
""".lstrip(),
        encoding="utf-8",
    )
    (root / ".env").write_text("DEMO_TOKEN=local-secret\n", encoding="utf-8")
    (generated_dir / "test_business.py").write_text("def test_generated():\n    pass\n", encoding="utf-8")

    result = {
        "run_id": "run-1",
        "status": "COMPLETED",
        "timestamp": "2026-08-24T10:00:00-05:00",
        "duration_seconds": 0.42,
        "summary": {"passed": 1, "failed": 0, "error": 0},
        "cases": [{"case_id": "TC-ORD-001", "outcome": "passed"}],
        "run_scope": {
            "type": "suite_file",
            "target": "demo",
            "module": "orders",
            "suite": "orders_smoke",
        },
    }
    (report_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")
    (report_dir / "report.md").write_text("# orders_smoke\n\n1 passed\n", encoding="utf-8")
    latest_dir = report_dir.parent.parent / "latest"
    latest_dir.mkdir()
    (latest_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")
    return root
