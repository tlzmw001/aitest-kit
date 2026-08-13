from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from aitest_kit.codegen.emitter import emit_file
from aitest_kit.codegen.planner import build_file_ir
from aitest_kit.codegen.profile_validator import validate_profile_suite
from aitest_kit.codegen.suite import load_suite_context_for_paths, parse_suite_case_file
from aitest_kit.registry import load_module_context, load_target_context


def _write_canonical_workspace(root: Path) -> Path:
    target_dir = root / "test_workspace" / "targets" / "demo"
    module_dir = target_dir / "modules" / "health"
    suite_dir = root / "test_workspace" / "suites" / "demo" / "health_smoke"
    module_dir.mkdir(parents=True)
    suite_dir.mkdir(parents=True)

    for package_dir in (
        root / "test_workspace",
        root / "test_workspace" / "targets",
        target_dir,
        target_dir / "modules",
        module_dir,
    ):
        (package_dir / "__init__.py").write_text("", encoding="utf-8")

    (target_dir / "target.yaml").write_text(
        """target: demo
defaults:
  module_dir: test_workspace/targets/demo/modules
  suite_dir: test_workspace/suites/demo
  generated_dir: test_workspace/generated/demo
  reports_dir: test_workspace/reports/demo
""",
        encoding="utf-8",
    )
    (module_dir / "module.yaml").write_text(
        """target: demo
module: health
module_type: multi_endpoint
registered_suites:
  - manifest: test_workspace/suites/demo/health_smoke/suite.yaml
""",
        encoding="utf-8",
    )
    (module_dir / "profile.md").write_text("```yaml\n{}\n```\n", encoding="utf-8")
    (module_dir / "harness.py").write_text(
        "class HealthHarness:\n    def status(self):\n        return {'status': 'ok'}\n",
        encoding="utf-8",
    )
    (module_dir / "fixture.py").write_text(
        """import pytest

from .harness import HealthHarness


@pytest.fixture
def _private_seed() -> int:
    return 42


@pytest.fixture
def setup_health(_private_seed: int) -> HealthHarness:
    assert _private_seed == 42
    return HealthHarness()
""",
        encoding="utf-8",
    )
    (suite_dir / "suite.yaml").write_text(
        """target: demo
module: health
suite: health_smoke
case_files:
  - business.md
""",
        encoding="utf-8",
    )
    (suite_dir / "business.md").write_text(
        """# health cases

## 一、冒烟

### TC-HEALTH-001：health ok
- **优先级**：P0
- **断言**：`response.status == \"ok\"`
""",
        encoding="utf-8",
    )
    (suite_dir / "profile_health_smoke_suite.md").write_text(
        """```yaml
profile_scope: case_suite
parent_module: health
suite: health_smoke
case_flows:
  TC-HEALTH-001:
    steps:
      - call: harness.status
        save_as: resp
      - assert: 'assert resp["status"] == "ok"'
```
""",
        encoding="utf-8",
    )
    return suite_dir / "suite.yaml"


def test_module_context_derives_canonical_harness_binding(tmp_path):
    suite_file = _write_canonical_workspace(tmp_path)
    target = load_target_context("demo", workspace_root=tmp_path)
    module = load_module_context(target, "health")

    module_dir = tmp_path / "test_workspace" / "targets" / "demo" / "modules" / "health"
    assert suite_file.exists()
    assert module.diagnostics == []
    assert module.config_path == module_dir / "module.yaml"
    assert module.profile_path == module_dir / "profile.md"
    assert module.fixture_path == module_dir / "fixture.py"
    assert module.harness_path == module_dir / "harness.py"
    assert module.binding.fixture_name == "setup_health"
    assert module.binding.object_name == "harness"
    assert module.binding.fixture_module == (
        "test_workspace.targets.demo.modules.health.fixture"
    )
    assert module.binding.fixture_import == (
        "from test_workspace.targets.demo.modules.health.fixture import setup_health"
    )


def test_suite_flow_gets_harness_binding_from_module_registry(tmp_path, monkeypatch):
    suite_file = _write_canonical_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)

    context = load_suite_context_for_paths(suite_file)
    validation = validate_profile_suite(suite_file)
    assert validation.errors == []
    parse_result = parse_suite_case_file(context.case_files[0], context.module)
    file_ir = build_file_ir(
        parse_result,
        "business",
        profile_path=context.runtime_profile,
    )

    assert context.module_binding is not None
    assert context.runtime_profile.module_binding == context.module_binding
    assert context.runtime_profile.data.get("extra_imports") in (None, [])
    assert file_ir.cases[0].fixtures == ["setup_health"]
    assert file_ir.cases[0].case_flow is not None
    assert file_ir.cases[0].case_flow.fixture == "setup_health"
    assert file_ir.cases[0].case_flow.object_name == "harness"

    output_dir = tmp_path / "test_workspace" / "generated" / "demo"
    result = emit_file(
        parse_result,
        "business",
        profile_path=context.runtime_profile,
        output_dir=output_dir,
    )
    assert result.diagnostics == []
    generated = Path(result.output_path).read_text(encoding="utf-8")
    assert (
        'pytest_plugins = ["test_workspace.targets.demo.modules.health.fixture"]'
        in generated
    )
    assert "def test_tc_health_001(self, setup_health):" in generated
    assert "harness = setup_health" in generated
    assert "resp = harness.status()" in generated

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        part
        for part in (
            str(tmp_path),
            str(Path(__file__).resolve().parents[1]),
            env.get("PYTHONPATH", ""),
        )
        if part
    )
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", str(result.output_path), "--collect-only", "-q"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert collected.returncode == 0, collected.stdout + collected.stderr
    assert "1 test collected" in collected.stdout
