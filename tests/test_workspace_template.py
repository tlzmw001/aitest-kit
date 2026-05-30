from __future__ import annotations

import hashlib
import json
from pathlib import Path

from click.testing import CliRunner

from aitest_kit.cli import main


def test_repo_does_not_keep_legacy_root_template_copy():
    assert not Path("templates/project_workspace").exists()


def _write_demo_module(workspace: Path) -> None:
    target_dir = workspace / "test_workspace" / "targets" / "demo_target"
    module_dir = target_dir / "modules"
    fixture_dir = target_dir / "fixtures"
    profile_dir = target_dir / "profiles"
    suite_dir = workspace / "test_workspace" / "suites" / "demo_target" / "demo_smoke"
    module_dir.mkdir(parents=True, exist_ok=True)
    fixture_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)
    suite_dir.mkdir(parents=True, exist_ok=True)

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
    (module_dir / "demo.yaml").write_text(
        """target: demo_target
module: demo
module_type: standard_http
fixture:
  file: demo.py
  default_fixture: setup_demo
registered_suites:
  - suite: demo_smoke
    manifest: test_workspace/suites/demo_target/demo_smoke/suite.yaml
    status: active
""",
        encoding="utf-8",
    )
    (fixture_dir / "demo.py").write_text(
        """import pytest


class DemoClient:
    def health(self):
        return {"code": 0}


@pytest.fixture
def setup_demo():
    return DemoClient()
""",
        encoding="utf-8",
    )
    (profile_dir / "profile_demo.md").write_text(
        "```yaml\nmodule_type: standard_http\n```\n",
        encoding="utf-8",
    )
    (suite_dir / "business.md").write_text(
        """# demo 业务测试用例

## 共享配置

**接口**：`GET /health`

---

## 一、基础场景

### TC-DEMO-001：demo generated case
- **优先级**：P1
- **断言**：`response.code == 0`
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
      - assert: 'assert resp["code"] == 0'
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


def test_init_creates_workspace_from_single_package_template(tmp_path):
    target = tmp_path / "project"
    result = CliRunner().invoke(main, ["init", "--target", str(target)])

    assert result.exit_code == 0
    assert (target / "README.md").exists()
    assert (target / "AGENTS.md").exists()
    assert (target / "CLAUDE.md").exists()
    assert (target / "skills" / "README.md").exists()
    assert (target / "skills" / "test-codegen" / "SKILL.md").exists()
    assert not (target / ".codex" / "skills").exists()
    assert not (target / ".claude" / "skills").exists()
    assert not (target / ".agents" / "skills").exists()
    assert (target / "docs" / ".gitkeep").exists()
    assert (target / "aitest_config" / "aitest.yaml").exists()
    assert (target / "aitest_config" / "schemas" / "codegen_profile.schema.json").exists()
    assert (target / "test_workspace" / "targets" / ".gitkeep").exists()
    assert (target / "test_workspace" / "suites" / ".gitkeep").exists()
    assert (target / "test_workspace" / "generated" / ".gitkeep").exists()
    assert (target / "test_workspace" / "tasks" / ".gitkeep").exists()
    assert not (target / "aitest_config" / "config.yaml").exists()
    assert not (target / "aitest_config" / "project_config.yaml").exists()
    assert not (target / "test_workspace" / "casesuites").exists()
    assert not (target / "test_workspace" / "tests" / "fixtures").exists()
    metadata = target / ".aitest" / "workspace.json"
    assert metadata.exists()
    manifest = json.loads(metadata.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["template_files"]["README.md"]["sha256"]
    assert not (target / "__init__.py").exists()
    assert not list(target.rglob(".DS_Store"))
    assert "Workspace initialized:" in result.output


def test_init_refuses_to_overwrite_template_managed_files(tmp_path):
    target = tmp_path / "project"
    target.mkdir()
    (target / "README.md").write_text("keep me\n", encoding="utf-8")

    result = CliRunner().invoke(main, ["init", "--target", str(target)])

    assert result.exit_code != 0
    assert "Use --force to overwrite" in result.output
    assert (target / "README.md").read_text(encoding="utf-8") == "keep me\n"


def test_init_accepts_existing_template_parent_directory(tmp_path):
    target = tmp_path / "project"
    (target / ".claude").mkdir(parents=True)

    result = CliRunner().invoke(main, ["init", "--target", str(target)])

    assert result.exit_code == 0
    assert (target / ".claude").is_dir()
    assert not (target / ".claude" / "skills").exists()
    assert (target / "skills" / "test-codegen" / "SKILL.md").exists()


def test_init_reports_file_blocking_template_directory(tmp_path):
    target = tmp_path / "project"
    target.mkdir()
    (target / "skills").write_text("not a directory\n", encoding="utf-8")

    result = CliRunner().invoke(main, ["init", "--target", str(target)])

    assert result.exit_code != 0
    assert "target contains file(s) where AITest needs directories: skills" in result.output
    assert "Traceback" not in result.output
    assert (target / "skills").read_text(encoding="utf-8") == "not a directory\n"


def test_init_force_overwrites_template_managed_files(tmp_path):
    target = tmp_path / "project"
    target.mkdir()
    (target / "README.md").write_text("old\n", encoding="utf-8")

    result = CliRunner().invoke(main, ["init", "--target", str(target), "--force"])

    assert result.exit_code == 0
    assert "overwritten:" in result.output
    readme = (target / "README.md").read_text(encoding="utf-8")
    assert "# AITest Workspace" in readme
    assert "目标系统的 AITest 测试工作区" in readme


def test_codegen_uses_workspace_for_profile_gate_and_generated_output(tmp_path):
    target = tmp_path / "project"
    runner = CliRunner()
    init_result = runner.invoke(main, ["init", "--target", str(target)])
    assert init_result.exit_code == 0
    _write_demo_module(target)
    suite_file = target / "test_workspace" / "suites" / "demo_target" / "demo_smoke" / "suite.yaml"

    validate = runner.invoke(main, ["codegen", "--suite-file", str(suite_file), "--workspace", str(target), "--validate-profile"])
    assert validate.exit_code == 0
    assert "Profile validation summary: suites=1, errors=0, warnings=0" in validate.output

    generate = runner.invoke(main, ["codegen", "--suite-file", str(suite_file), "--workspace", str(target)])
    assert generate.exit_code == 0
    generated = target / "test_workspace" / "generated" / "demo_target" / "test_demo_demo_smoke_business.py"
    assert generated.exists()
    assert not Path("test_workspace/generated/demo_target/test_demo_demo_smoke_business.py").exists()


def test_workspace_option_reports_missing_directory():
    result = CliRunner().invoke(main, ["codegen", "--suite-file", "suite.yaml", "--workspace", "/path/does/not/exist"])

    assert result.exit_code != 0
    assert "workspace does not exist" in result.output


def test_empty_workspace_doctor_gives_next_step(tmp_path):
    target = tmp_path / "project"
    runner = CliRunner()
    init_result = runner.invoke(main, ["init", "--target", str(target)])
    assert init_result.exit_code == 0

    result = runner.invoke(main, ["doctor", "--workspace", str(target)])

    assert result.exit_code == 0
    assert "[INFO] target registry: no target registry entries found" in result.output
    assert "fail=0" in result.output


def test_cli_help_matches_workspace_product_flow():
    runner = CliRunner()

    root_help = runner.invoke(main, ["--help"])
    assert root_help.exit_code == 0
    assert "Markdown cases, codegen, and pytest reports" in root_help.output
    assert "Command map:" in root_help.output
    assert "registry  wire suites into module/target/all aggregation" in root_help.output

    init_help = runner.invoke(main, ["init", "--help"])
    assert init_help.exit_code == 0
    assert "AITest workspace skeleton" in init_help.output
    assert "After init:" in init_help.output
    assert "aitest doctor" in init_help.output

    codegen_help = runner.invoke(main, ["codegen", "--help"])
    assert codegen_help.exit_code == 0
    assert "Markdown test suites/tasks" in codegen_help.output
    assert "codegen_profile JSON Schema and semantics" in codegen_help.output
    assert "another AITest workspace root" in codegen_help.output
    assert "Typical suite flow:" in codegen_help.output
    assert "--check never writes generated pytest" in codegen_help.output

    doctor_help = runner.invoke(main, ["doctor", "--help"])
    assert doctor_help.exit_code == 0
    assert "Diagnose workspace layout, registries" in doctor_help.output
    assert "target/module/suite registry" in doctor_help.output
    assert "fixture environment variable hints" in doctor_help.output

    upgrade_help = runner.invoke(main, ["upgrade", "--help"])
    assert upgrade_help.exit_code == 0
    assert "Upgrade template-managed files" in upgrade_help.output

    run_help = runner.invoke(main, ["run", "--help"])
    assert run_help.exit_code == 0
    assert "freshness check" in run_help.output
    assert "another AITest workspace root" in run_help.output
    assert "AITEST_ENV_FILE=/tmp/test.env" in run_help.output
    assert "--case-id TC-XXX-001" in run_help.output

    report_help = runner.invoke(main, ["report", "--help"])
    assert report_help.exit_code == 0
    assert "existing result.json" in report_help.output
    assert "Report buckets:" in report_help.output
    assert "reports/<target>/<module>/suites/<suite>/" in report_help.output

    register_suite_help = runner.invoke(main, ["registry", "register-suite", "--help"])
    assert register_suite_help.exit_code == 0
    assert "Registration is only needed" in register_suite_help.output
    assert "--target <target>" in register_suite_help.output

    task_create_help = runner.invoke(main, ["task", "create", "--help"])
    assert task_create_help.exit_code == 0
    assert "explicit suite files" in task_create_help.output
    assert "does not require" in task_create_help.output
    assert "registered under their modules" in task_create_help.output


def test_upgrade_check_reports_up_to_date_after_init(tmp_path):
    target = tmp_path / "project"
    runner = CliRunner()
    assert runner.invoke(main, ["init", "--target", str(target)]).exit_code == 0

    result = runner.invoke(main, ["upgrade", "--workspace", str(target), "--check"])

    assert result.exit_code == 0
    assert "Workspace is up to date." in result.output
    assert "Summary:" in result.output
    assert "[UPDATE]" not in result.output
    assert "[LOCAL]" not in result.output


def test_upgrade_apply_restores_missing_safe_template_file(tmp_path):
    target = tmp_path / "project"
    runner = CliRunner()
    assert runner.invoke(main, ["init", "--target", str(target)]).exit_code == 0
    skill = target / "skills" / "test-codegen" / "SKILL.md"
    skill.unlink()

    result = runner.invoke(main, ["upgrade", "--workspace", str(target), "--apply"])

    assert result.exit_code == 0
    assert "[NEW] skills/test-codegen/SKILL.md" in result.output
    assert "created=1" in result.output
    assert skill.exists()


def test_upgrade_apply_updates_old_clean_template_file_and_backs_up(tmp_path):
    target = tmp_path / "project"
    runner = CliRunner()
    assert runner.invoke(main, ["init", "--target", str(target)]).exit_code == 0

    readme = target / "README.md"
    old_content = "# old clean template\n"
    readme.write_text(old_content, encoding="utf-8")
    _set_manifest_hash(target, "README.md", old_content)

    result = runner.invoke(main, ["upgrade", "--workspace", str(target), "--apply"])

    assert result.exit_code == 0
    assert "[UPDATE] README.md" in result.output
    assert "updated=1" in result.output
    assert "# AITest Workspace" in readme.read_text(encoding="utf-8")
    backups = list((target / ".aitest" / "backups").glob("upgrade-*/README.md"))
    assert backups
    assert backups[0].read_text(encoding="utf-8") == old_content


def test_upgrade_apply_does_not_overwrite_local_modified_file(tmp_path):
    target = tmp_path / "project"
    runner = CliRunner()
    assert runner.invoke(main, ["init", "--target", str(target)]).exit_code == 0

    readme = target / "README.md"
    local_content = "# user modified\n"
    readme.write_text(local_content, encoding="utf-8")

    result = runner.invoke(main, ["upgrade", "--workspace", str(target), "--apply"])

    assert result.exit_code == 0
    assert "[LOCAL] README.md" in result.output
    assert "updated=0" in result.output
    assert readme.read_text(encoding="utf-8") == local_content


def _set_manifest_hash(target: Path, relative: str, content: str) -> None:
    metadata_path = target / ".aitest" / "workspace.json"
    manifest = json.loads(metadata_path.read_text(encoding="utf-8"))
    manifest["template_files"][relative]["sha256"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    metadata_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
