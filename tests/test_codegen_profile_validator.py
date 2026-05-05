from pathlib import Path

from click.testing import CliRunner

from aitest_kit.codegen.cli import codegen
from aitest_kit.codegen.profile_validator import validate_profile_module
from aitest_kit.codegen.project_config import ProjectConfig


def _write_case_file(cases_dir: Path, module: str, case_id: str = "TC-DEMO-001") -> None:
    module_dir = cases_dir / module
    module_dir.mkdir(parents=True)
    (module_dir / "business.md").write_text(
        f"""# {module} 业务测试用例

## 共享配置

**通用断言**：`response.code == 0`

---

## 一、基础场景

### {case_id}：demo case
- **优先级**：P1
- **断言**：`response.code == 0`
""",
        encoding="utf-8",
    )


def _write_profile(profile_dir: Path, module: str, yaml_body: str) -> None:
    profile_dir.mkdir(parents=True)
    (profile_dir / f"codegen_profile_{module}.md").write_text(
        f"```yaml\n{yaml_body}```\n",
        encoding="utf-8",
    )


def _project(module_type: str = "standard_recommend") -> ProjectConfig:
    return ProjectConfig(
        module_types={
            "standard_recommend": {"description": "standard"},
            "isolated_service": {"description": "isolated", "requires": ["case_bodies"]},
        },
        modules={"demo": {"module_type": module_type}},
    )


def test_validate_profile_module_accepts_current_repo_profiles():
    result = CliRunner().invoke(codegen, ["--all", "--validate-profile"])

    assert result.exit_code == 0
    assert "Profile validation summary: modules=10, errors=0, warnings=0" in result.output


def test_validate_profile_cli_writes_report_artifacts(tmp_path):
    report_dir = tmp_path / "reports"

    result = CliRunner().invoke(
        codegen,
        [
            "ab_service",
            "--validate-profile",
            "--write-report",
            "--report-dir",
            str(report_dir),
        ],
    )

    assert result.exit_code == 0
    md_path = report_dir / "ab_service_profile_validation.md"
    json_path = report_dir / "ab_service_profile_validation.json"
    assert md_path.exists()
    assert json_path.exists()
    assert "# Profile Validation Report: ab_service" in md_path.read_text(encoding="utf-8")
    assert '"module": "ab_service"' in json_path.read_text(encoding="utf-8")
    assert "Profile validation artifacts written:" in result.output


def test_profile_validator_rejects_conflict_and_naked_assert(tmp_path):
    cases_dir = tmp_path / "cases"
    profile_dir = tmp_path / "fixtures"
    _write_case_file(cases_dir, "demo")
    _write_profile(
        profile_dir,
        "demo",
        """case_bodies:
  TC-DEMO-001: |
    assert True
case_flows:
  TC-DEMO-001:
    fixture: setup_demo
    steps:
      - call: setup_demo
        kwargs:
          case_id: "TC-DEMO-001"
        save_as: case
      - assert: "`resp == ERR`"
""",
    )

    report = validate_profile_module(
        "demo",
        cases_dir=cases_dir,
        profile_dir=profile_dir,
        project=_project(),
    )

    messages = "\n".join(diag.message for diag in report.errors)
    assert "defined in both case_bodies and case_flows" in messages
    assert "must start with 'assert '" in messages


def test_profile_validator_rejects_unknown_case_reference(tmp_path):
    cases_dir = tmp_path / "cases"
    profile_dir = tmp_path / "fixtures"
    _write_case_file(cases_dir, "demo")
    _write_profile(
        profile_dir,
        "demo",
        """request_overrides:
  TC-DEMO-999:
    user_id: u_missing
""",
    )

    report = validate_profile_module(
        "demo",
        cases_dir=cases_dir,
        profile_dir=profile_dir,
        project=_project(),
    )

    assert any(diag.code == "E505" for diag in report.errors)
    assert any("does not exist" in diag.message for diag in report.errors)


def test_profile_validator_rejects_schema_unknown_nested_field(tmp_path):
    cases_dir = tmp_path / "cases"
    profile_dir = tmp_path / "fixtures"
    _write_case_file(cases_dir, "demo")
    _write_profile(
        profile_dir,
        "demo",
        """case_flows:
  TC-DEMO-001:
    fixture: setup_demo
    steps:
      - call: setup_demo
        save_as: case
        unexpected: true
""",
    )

    report = validate_profile_module(
        "demo",
        cases_dir=cases_dir,
        profile_dir=profile_dir,
        project=_project(),
    )

    assert any(diag.code == "E501" for diag in report.errors)
    assert any("profile schema violation" in diag.message for diag in report.errors)


def test_profile_validator_checks_module_type_requirements(tmp_path):
    cases_dir = tmp_path / "cases"
    profile_dir = tmp_path / "fixtures"
    _write_case_file(cases_dir, "demo")
    _write_profile(profile_dir, "demo", "extra_imports: []\n")

    report = validate_profile_module(
        "demo",
        cases_dir=cases_dir,
        profile_dir=profile_dir,
        project=_project("isolated_service"),
    )

    assert any(diag.code == "E504" for diag in report.errors)
    assert any("requires case_bodies or case_flows" in diag.message for diag in report.errors)


def test_codegen_hard_gate_blocks_generation_before_emitter(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        cases_dir = Path("test_workspace/cases")
        profile_dir = Path("test_workspace/tests/fixtures")
        _write_case_file(cases_dir, "demo")
        _write_profile(
            profile_dir,
            "demo",
            """case_flows:
  TC-DEMO-001:
    fixture: setup_demo
    steps:
      - assert: "`resp == ERR`"
""",
        )
        result = runner.invoke(codegen, ["demo"])

    assert result.exit_code == 1
    assert "Profile gate blocked codegen" in result.output
    assert "must start with 'assert '" in result.output
