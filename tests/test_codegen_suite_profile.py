from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from aitest_kit.codegen.cli import codegen
from aitest_kit.codegen.suite import (
    load_suite_context,
    suite_generated_path,
    suite_output_file_type,
)


def _write_module_profile(root: Path) -> None:
    fixture_dir = root / "test_workspace" / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "codegen_profile_gateway_api.md").write_text(
        """```yaml
module_type: multi_endpoint
extra_imports:
  - "from test_workspace.tests.fixtures.gateway_api import setup_gateway_api"
default_fixture: setup_gateway_api
default_object: client
```
""",
        encoding="utf-8",
    )


def _write_suite(
    root: Path,
    *,
    with_manifest: bool = True,
    profile_name: str = "codegen_profile_quota_billing_v2_suite.md",
    case_id: str = "TC-GW-041",
    profile_case_id: str = "TC-GW-041",
) -> Path:
    suite_dir = root / "test_workspace" / "casesuites" / "quota_billing_v2"
    suite_dir.mkdir(parents=True, exist_ok=True)
    if with_manifest:
        (suite_dir / "aitest_suite.yaml").write_text(
            f"""module: gateway_api
suite: quota_billing_v2
case_files:
  - quota_billing_business.md
profile: {profile_name}
""",
            encoding="utf-8",
        )
    (suite_dir / "quota_billing_business.md").write_text(
        f"""# quota billing cases

## 共享配置

**接口**：`GET /health`

---

## 一、冒烟

### {case_id}：health ok
- **优先级**：P0
- **断言**：`response.status == "ok"`
""",
        encoding="utf-8",
    )
    (suite_dir / profile_name).write_text(
        f"""```yaml
profile_scope: case_suite
parent_module: gateway_api
suite: quota_billing_v2
case_flows:
  {profile_case_id}:
    fixture: setup_gateway_api
    object: client
    steps:
      - call: client.health
        save_as: resp
      - assert: 'assert resp["status"] == "ok"'
```
""",
        encoding="utf-8",
    )
    return suite_dir


def test_codegen_cases_suite_validates_dumps_generates_and_checks(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        root = Path(cwd)
        _write_module_profile(root)
        suite_dir = _write_suite(root)

        validate = runner.invoke(codegen, ["--cases", str(suite_dir), "--validate-profile"])
        assert validate.exit_code == 0
        assert "Profile validation summary: suites=1, errors=0, warnings=0" in validate.output

        dump = runner.invoke(codegen, ["--cases", str(suite_dir), "--dump-ir"])
        assert dump.exit_code == 0
        payload = json.loads(dump.output)
        case = payload["suites"][0]["files"][0]["cases"][0]
        assert payload["suites"][0]["module"] == "gateway_api"
        assert payload["suites"][0]["suite"] == "quota_billing_v2"
        assert case["strategy"] == "structured_case_flow"

        generate = runner.invoke(codegen, ["--cases", str(suite_dir)])
        assert generate.exit_code == 0
        generated = root / "test_workspace" / "tests" / "generated" / (
            "test_gateway_api_quota_billing_v2_quota_billing_business.py"
        )
        assert generated.exists()
        assert "# Auto-generated from test_workspace/casesuites/quota_billing_v2" in generated.read_text(encoding="utf-8")

        check = runner.invoke(codegen, ["--cases", str(suite_dir), "--check"])
        assert check.exit_code == 0
        assert "All generated files are up to date." in check.output

        explain = runner.invoke(codegen, ["--cases", str(suite_dir), "--explain", "TC-GW-041"])
        assert explain.exit_code == 0
        assert "case_id: TC-GW-041" in explain.output
        assert "strategy: structured_case_flow" in explain.output

        report_dir = root / "reports"
        health = runner.invoke(
            codegen,
            ["--cases", str(suite_dir), "--health-report", "--write-report", "--report-dir", str(report_dir)],
        )
        assert health.exit_code == 0
        assert "suite: quota_billing_v2" in health.output
        assert (report_dir / "codegen_health_report.md").exists()
        assert (report_dir / "codegen_health_report.json").exists()


def test_codegen_suite_file_and_task_manifest_reuse_suite_pipeline(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        root = Path(cwd)
        _write_module_profile(root)
        suite_dir = _write_suite(root, with_manifest=False, profile_name="profile_quota_billing_v2_suite.md")
        suite_file = suite_dir / "suite.yaml"
        suite_file.write_text(
            """target: sub2api
module: gateway_api
suite: quota_billing_v2
case_files:
  - quota_billing_business.md
profile: profile_quota_billing_v2_suite.md
""",
            encoding="utf-8",
        )

        validate = runner.invoke(codegen, ["--suite-file", str(suite_file), "--validate-profile"])
        assert validate.exit_code == 0, validate.output
        assert "Profile validation summary: suites=1, errors=0, warnings=0" in validate.output

        generate = runner.invoke(codegen, ["--suite-file", str(suite_file)])
        assert generate.exit_code == 0, generate.output
        generated = root / "test_workspace" / "tests" / "generated" / (
            "test_gateway_api_quota_billing_v2_quota_billing_business.py"
        )
        assert generated.exists()

        task_dir = root / "test_workspace" / "tasks"
        task_dir.mkdir(parents=True)
        task_file = task_dir / "release_regression.yaml"
        task_file.write_text(
            f"""task: release_regression
units:
  - target: sub2api
    module: gateway_api
    suite: quota_billing_v2
    suite_file: {suite_file}
""",
            encoding="utf-8",
        )

        check = runner.invoke(codegen, ["--task", str(task_file), "--check"])
        assert check.exit_code == 0, check.output
        assert "Task: release_regression" in check.output
        assert "All generated files are up to date." in check.output


def test_suite_generated_path_uses_shared_naming_rule(tmp_path):
    root = tmp_path
    _write_module_profile(root)
    suite_dir = _write_suite(root, with_manifest=False, profile_name="profile_quota_billing_v2_suite.md")
    suite_file = suite_dir / "suite.yaml"
    suite_file.write_text(
        """target: sub2api
module: gateway_api
suite: quota_billing_v2
case_files:
  - quota_billing_business.md
profile: profile_quota_billing_v2_suite.md
""",
        encoding="utf-8",
    )

    context = load_suite_context(
        suite_file,
        profile_dir=root / "test_workspace" / "tests" / "fixtures",
    )
    case_file = context.case_files[0]

    assert suite_output_file_type(context, case_file) == "quota_billing_v2_quota_billing_business"
    assert suite_generated_path(root / "generated", context, case_file) == (
        root / "generated" / "test_gateway_api_quota_billing_v2_quota_billing_business.py"
    )


def test_suite_yaml_requires_explicit_target_and_case_files(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        root = Path(cwd)
        _write_module_profile(root)
        suite_dir = _write_suite(root, with_manifest=False, profile_name="profile_quota_billing_v2_suite.md")
        suite_file = suite_dir / "suite.yaml"
        suite_file.write_text(
            """module: gateway_api
suite: quota_billing_v2
profile: profile_quota_billing_v2_suite.md
""",
            encoding="utf-8",
        )

        validate = runner.invoke(codegen, ["--suite-file", str(suite_file), "--validate-profile"])

        assert validate.exit_code == 1
        assert "E610" in validate.output
        assert "suite.yaml requires target" in validate.output
        assert "suite.yaml requires case_files" in validate.output


def test_suite_yaml_rejects_generation_and_execution_fields(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        root = Path(cwd)
        _write_module_profile(root)
        suite_dir = _write_suite(root, with_manifest=False, profile_name="profile_quota_billing_v2_suite.md")
        suite_file = suite_dir / "suite.yaml"
        suite_file.write_text(
            """target: sub2api
module: gateway_api
suite: quota_billing_v2
case_files:
  - quota_billing_business.md
profile: profile_quota_billing_v2_suite.md
case_flows: {}
env_file: .env.test
""",
            encoding="utf-8",
        )

        validate = runner.invoke(codegen, ["--suite-file", str(suite_file), "--validate-profile"])

        assert validate.exit_code == 1
        assert "E610" in validate.output
        assert "must not contain generation or execution fields" in validate.output
        assert "case_flows" in validate.output
        assert "env_file" in validate.output


def test_codegen_cases_allows_explicit_module_without_manifest(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        root = Path(cwd)
        _write_module_profile(root)
        suite_dir = _write_suite(root, with_manifest=False, profile_name="codegen_profile_quota_billing_v2_suite.md")

        result = runner.invoke(
            codegen,
            ["--module", "gateway_api", "--cases", str(suite_dir), "--validate-profile"],
        )

        assert result.exit_code == 0
        assert "Suite: quota_billing_v2" in result.output


def test_codegen_cases_rejects_suite_profile_filename_without_suite_suffix(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        root = Path(cwd)
        _write_module_profile(root)
        suite_dir = _write_suite(root, profile_name="profile.md")

        result = runner.invoke(codegen, ["--cases", str(suite_dir), "--validate-profile"])

        assert result.exit_code == 1
        assert "filename must end with _suite.md" in result.output


def test_codegen_cases_rejects_unknown_suite_case_reference(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        root = Path(cwd)
        _write_module_profile(root)
        suite_dir = _write_suite(root, profile_case_id="TC-GW-999")

        result = runner.invoke(codegen, ["--cases", str(suite_dir), "--validate-profile"])

        assert result.exit_code == 1
        assert "case id does not exist" in result.output


def test_codegen_cases_rejects_generated_source_conflict(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        root = Path(cwd)
        _write_module_profile(root)
        suite_dir = _write_suite(root)
        generated_dir = root / "test_workspace" / "tests" / "generated"
        generated_dir.mkdir(parents=True, exist_ok=True)
        (generated_dir / "test_gateway_api_quota_billing_v2_quota_billing_business.py").write_text(
            "# Auto-generated from other_suite/quota_billing_business.md\n",
            encoding="utf-8",
        )

        result = runner.invoke(codegen, ["--cases", str(suite_dir)])

        assert result.exit_code == 1
        assert "generated output conflict" in result.output


def test_codegen_cases_suite_analyzes_promotion_and_writes_patch(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        root = Path(cwd)
        _write_module_profile(root)
        suite_dir = root / "test_workspace" / "casesuites" / "promotion_smoke"
        suite_dir.mkdir(parents=True, exist_ok=True)
        (suite_dir / "aitest_suite.yaml").write_text(
            """module: gateway_api
suite: promotion_smoke
case_files:
  - business.md
profile: codegen_profile_promotion_smoke_suite.md
""",
            encoding="utf-8",
        )
        (suite_dir / "business.md").write_text(
            """# promotion smoke

## 共享配置

**接口**：`GET /health`

---

## 一、重复流程

### TC-GW-071：case body one
- **优先级**：P1
- **断言**：`response.status == "ok"`

### TC-GW-072：case body two
- **优先级**：P1
- **断言**：`response.status == "ok"`

### TC-GW-073：case body three
- **优先级**：P1
- **断言**：`response.status == "ok"`
""",
            encoding="utf-8",
        )
        (suite_dir / "codegen_profile_promotion_smoke_suite.md").write_text(
            """```yaml
profile_scope: case_suite
parent_module: gateway_api
suite: promotion_smoke
case_bodies:
  TC-GW-071: |
    resp = client.health()
    assert resp["status"] == "ok"
  TC-GW-072: |
    resp = client.health()
    assert resp["status"] == "ok"
  TC-GW-073: |
    resp = client.health()
    assert resp["status"] == "ok"
```
""",
            encoding="utf-8",
        )

        analyze = runner.invoke(codegen, ["--cases", str(suite_dir), "--analyze-promotion"])
        assert analyze.exit_code == 0
        assert "suite: promotion_smoke" in analyze.output
        assert "candidate: true" in analyze.output

        out_dir = root / "promotion-reports"
        patch = runner.invoke(
            codegen,
            ["--cases", str(suite_dir), "--suggest-promotion-patch", "--report-dir", str(out_dir)],
        )
        assert patch.exit_code == 0
        assert "Promotion artifacts written:" in patch.output
        assert (out_dir / "gateway_api_promotion_smoke_promotion_report.md").exists()
        assert (out_dir / "gateway_api_promotion_smoke_promotion_patch.md").exists()
