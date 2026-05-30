from __future__ import annotations

import yaml
from click.testing import CliRunner

from aitest_kit.cli import main


def test_registry_register_suite_adds_active_suite(tmp_path):
    workspace, suite_file = _workspace_with_suite(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "registry",
            "register-suite",
            "--workspace",
            str(workspace),
            "--target",
            "demo_target",
            "--module",
            "demo_module",
            "--suite-file",
            str(suite_file),
        ],
    )

    assert result.exit_code == 0, result.output
    module_data = _read_yaml(workspace / "test_workspace" / "targets" / "demo_target" / "modules" / "demo_module.yaml")
    assert module_data["registered_suites"] == [
        {
            "suite": "demo_smoke",
            "manifest": "test_workspace/suites/demo_target/demo_smoke/suite.yaml",
            "status": "active",
        }
    ]
    assert "aitest codegen --target demo_target --module demo_module --check" in result.output


def test_registry_register_suite_is_idempotent(tmp_path):
    workspace, suite_file = _workspace_with_suite(tmp_path)
    runner = CliRunner()
    args = [
        "registry",
        "register-suite",
        "--workspace",
        str(workspace),
        "--target",
        "demo_target",
        "--module",
        "demo_module",
        "--suite-file",
        str(suite_file),
    ]

    first = runner.invoke(main, args)
    second = runner.invoke(main, args)

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert "Already registered" in second.output
    module_data = _read_yaml(workspace / "test_workspace" / "targets" / "demo_target" / "modules" / "demo_module.yaml")
    assert len(module_data["registered_suites"]) == 1


def test_registry_register_suite_rejects_same_suite_different_manifest(tmp_path):
    workspace, suite_file = _workspace_with_suite(tmp_path)
    other_suite = _write_suite(workspace, "other_location", suite_name="demo_smoke")
    runner = CliRunner()
    base_args = [
        "registry",
        "register-suite",
        "--workspace",
        str(workspace),
        "--target",
        "demo_target",
        "--module",
        "demo_module",
    ]

    first = runner.invoke(main, base_args + ["--suite-file", str(suite_file)])
    second = runner.invoke(main, base_args + ["--suite-file", str(other_suite)])

    assert first.exit_code == 0, first.output
    assert second.exit_code != 0
    assert "different manifest" in second.output


def test_registry_register_suite_rejects_target_module_mismatch(tmp_path):
    workspace, suite_file = _workspace_with_suite(tmp_path, suite_target="other_target")
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "registry",
            "register-suite",
            "--workspace",
            str(workspace),
            "--target",
            "demo_target",
            "--module",
            "demo_module",
            "--suite-file",
            str(suite_file),
        ],
    )

    assert result.exit_code != 0
    assert "does not match target demo_target" in result.output


def test_task_create_writes_task_with_relative_suite_paths(tmp_path):
    workspace, suite_file = _workspace_with_suite(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "task",
            "create",
            "--workspace",
            str(workspace),
            "--name",
            "nightly_demo",
            "--suite-file",
            str(suite_file),
        ],
    )

    assert result.exit_code == 0, result.output
    task_path = workspace / "test_workspace" / "tasks" / "nightly_demo.yaml"
    task_data = _read_yaml(task_path)
    assert task_data == {
        "schema_version": 1,
        "task": "nightly_demo",
        "description": "",
        "units": [
            {
                "name": "demo_smoke",
                "suite_file": "../suites/demo_target/demo_smoke/suite.yaml",
            }
        ],
    }
    assert "aitest run --task-file test_workspace/tasks/nightly_demo.yaml" in result.output


def test_task_create_rejects_existing_file_without_overwrite(tmp_path):
    workspace, suite_file = _workspace_with_suite(tmp_path)
    task_path = workspace / "test_workspace" / "tasks" / "nightly_demo.yaml"
    task_path.write_text("schema_version: 1\n", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "task",
            "create",
            "--workspace",
            str(workspace),
            "--name",
            "nightly_demo",
            "--suite-file",
            str(suite_file),
        ],
    )

    assert result.exit_code != 0
    assert "already exists" in result.output


def _workspace_with_suite(
    tmp_path,
    *,
    suite_target: str = "demo_target",
):
    workspace = tmp_path / "workspace"
    target_dir = workspace / "test_workspace" / "targets" / "demo_target"
    (target_dir / "modules").mkdir(parents=True)
    (target_dir / "fixtures").mkdir()
    (target_dir / "profiles").mkdir()
    (target_dir / "helpers").mkdir()
    (workspace / "test_workspace" / "tasks").mkdir(parents=True)
    (target_dir / "target.yaml").write_text(
        """target: demo_target
defaults:
  module_dir: test_workspace/targets/demo_target/modules
  fixture_dir: test_workspace/targets/demo_target/fixtures
  helper_dir: test_workspace/targets/demo_target/helpers
  profile_dir: test_workspace/targets/demo_target/profiles
  suite_dir: test_workspace/suites/demo_target
  generated_dir: test_workspace/generated/demo_target
  reports_dir: test_workspace/reports/demo_target
""",
        encoding="utf-8",
    )
    (target_dir / "modules" / "demo_module.yaml").write_text(
        """target: demo_target
module: demo_module
module_type: multi_endpoint
fixture:
  file: demo_module.py
  default_fixture: setup_demo_module
profile:
  file: profile_demo_module.md
registered_suites: []
""",
        encoding="utf-8",
    )
    (target_dir / "fixtures" / "demo_module.py").write_text(
        "def setup_demo_module():\n    return object()\n",
        encoding="utf-8",
    )
    (target_dir / "profiles" / "profile_demo_module.md").write_text("# module profile\n", encoding="utf-8")
    suite_file = _write_suite(workspace, "demo_smoke", suite_target=suite_target)
    return workspace, suite_file


def _write_suite(
    workspace,
    dirname: str,
    *,
    suite_name: str = "demo_smoke",
    suite_target: str = "demo_target",
):
    suite_dir = workspace / "test_workspace" / "suites" / "demo_target" / dirname
    suite_dir.mkdir(parents=True)
    (suite_dir / "business.md").write_text("# business\n", encoding="utf-8")
    (suite_dir / f"profile_{suite_name}_suite.md").write_text("# suite profile\n", encoding="utf-8")
    suite_file = suite_dir / "suite.yaml"
    suite_file.write_text(
        f"""target: {suite_target}
module: demo_module
suite: {suite_name}
case_files:
  - business.md
profile: profile_{suite_name}_suite.md
""",
        encoding="utf-8",
    )
    return suite_file


def _read_yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))
