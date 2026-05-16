from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from aitest_kit.cli import main


def test_repo_does_not_keep_legacy_root_template_copy():
    assert not Path("templates/project_workspace").exists()


def _write_demo_module(workspace: Path) -> None:
    case_dir = workspace / "test_workspace" / "cases" / "demo"
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "business.md").write_text(
        """# demo 业务测试用例

## 共享配置

**接口**：`POST /demo`

**基础请求体（HTTP）**：

```json
{
  "user_id": "u_default",
  "reqId": "req_default",
  "value": 1
}
```

**通用断言**：`response.code == 0`

---

## 一、基础场景

### TC-DEMO-001：demo generated case
- **优先级**：P1
- **断言**：`response.code == 0`
""",
        encoding="utf-8",
    )

    fixture_dir = workspace / "test_workspace" / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "codegen_profile_demo.md").write_text(
        """```yaml
module_type: standard_http
```
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
    assert (target / ".codex" / "skills" / "test-codegen" / "SKILL.md").exists()
    assert (target / ".claude" / "skills" / "test-codegen" / "SKILL.md").exists()
    assert (target / ".agents" / "skills" / "test-codegen" / "SKILL.md").exists()
    assert (target / "docs" / ".gitkeep").exists()
    assert (target / "aitest_config" / "config.yaml").exists()
    assert (target / "aitest_config" / "schemas" / "codegen_profile.schema.json").exists()
    assert (target / "test_workspace" / "tests" / "helpers" / "http.py").exists()
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


def test_init_force_overwrites_template_managed_files(tmp_path):
    target = tmp_path / "project"
    target.mkdir()
    (target / "README.md").write_text("old\n", encoding="utf-8")

    result = CliRunner().invoke(main, ["init", "--target", str(target), "--force"])

    assert result.exit_code == 0
    assert "overwritten:" in result.output
    readme = (target / "README.md").read_text(encoding="utf-8")
    assert "# AITest 项目工作区" in readme
    assert "目标系统的测试工作区" in readme


def test_codegen_uses_workspace_for_profile_gate_and_generated_output(tmp_path):
    target = tmp_path / "project"
    runner = CliRunner()
    init_result = runner.invoke(main, ["init", "--target", str(target)])
    assert init_result.exit_code == 0
    _write_demo_module(target)

    validate = runner.invoke(main, ["codegen", "demo", "--workspace", str(target), "--validate-profile"])
    assert validate.exit_code == 0
    assert "Profile validation summary: modules=1, errors=0, warnings=0" in validate.output

    generate = runner.invoke(main, ["codegen", "demo", "--workspace", str(target)])
    assert generate.exit_code == 0
    generated = target / "test_workspace" / "tests" / "generated" / "test_demo_business.py"
    assert generated.exists()
    assert not Path("test_workspace/tests/generated/test_demo_business.py").exists()


def test_workspace_option_reports_missing_directory():
    result = CliRunner().invoke(main, ["codegen", "--all", "--workspace", "/path/does/not/exist"])

    assert result.exit_code != 0
    assert "workspace does not exist" in result.output


def test_empty_workspace_validate_profile_gives_next_step(tmp_path):
    target = tmp_path / "project"
    runner = CliRunner()
    init_result = runner.invoke(main, ["init", "--target", str(target)])
    assert init_result.exit_code == 0

    result = runner.invoke(main, ["codegen", "--all", "--workspace", str(target), "--validate-profile"])

    assert result.exit_code == 0
    assert "No modules found under the configured cases directory." in result.output
    assert "Next step: create test_workspace/cases/<module>/business.md" in result.output
    assert "Profile validation summary: modules=0, errors=0, warnings=0" in result.output


def test_cli_help_matches_workspace_product_flow():
    runner = CliRunner()

    root_help = runner.invoke(main, ["--help"])
    assert root_help.exit_code == 0
    assert "Markdown cases, codegen, and pytest reports" in root_help.output

    init_help = runner.invoke(main, ["init", "--help"])
    assert init_help.exit_code == 0
    assert "AITest workspace skeleton" in init_help.output

    codegen_help = runner.invoke(main, ["codegen", "--help"])
    assert codegen_help.exit_code == 0
    assert "Markdown test cases" in codegen_help.output
    assert "codegen_profile JSON Schema and semantics" in codegen_help.output
    assert "another AITest workspace root" in codegen_help.output

    doctor_help = runner.invoke(main, ["doctor", "--help"])
    assert doctor_help.exit_code == 0
    assert "Diagnose workspace layout" in doctor_help.output

    run_help = runner.invoke(main, ["run", "--help"])
    assert run_help.exit_code == 0
    assert "freshness check" in run_help.output
    assert "another AITest workspace root" in run_help.output

    report_help = runner.invoke(main, ["report", "--help"])
    assert report_help.exit_code == 0
    assert "existing result.json" in report_help.output
