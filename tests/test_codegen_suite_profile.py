from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from aitest_kit.codegen.cli import codegen


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


def test_codegen_cases_suite_profile_variables_render_runtime_lookup(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        root = Path(cwd)
        _write_module_profile(root)
        suite_dir = root / "test_workspace" / "casesuites" / "login_smoke"
        suite_dir.mkdir(parents=True, exist_ok=True)
        (suite_dir / "aitest_suite.yaml").write_text(
            """module: gateway_api
suite: login_smoke
case_files:
  - business.md
profile: codegen_profile_login_smoke_suite.md
""",
            encoding="utf-8",
        )
        (suite_dir / "business.md").write_text(
            """# login smoke

## 共享配置

**接口**：`POST /login`

---

## 一、登录

### TC-GW-051：login with profile variables
- **优先级**：P0
- **断言**：`response.status_code == 200`
""",
            encoding="utf-8",
        )
        (suite_dir / "codegen_profile_login_smoke_suite.md").write_text(
            """```yaml
profile_scope: case_suite
parent_module: gateway_api
suite: login_smoke
variables:
  defaults:
    base_url:
      env: SUB2API_BASE_URL
  cases:
    TC-GW-051:
      username:
        env: SUB2API_TEST_USER_EMAIL
      password:
        value: wrong-password
case_flows:
  TC-GW-051:
    fixture: setup_gateway_api
    object: client
    steps:
      - call: client.login
        kwargs:
          base_url:
            var: base_url
          username:
            var: username
          password:
            var: password
        save_as: resp
      - assert: "assert resp.status_code == 200"
```
""",
            encoding="utf-8",
        )

        validate = runner.invoke(codegen, ["--cases", str(suite_dir), "--validate-profile"])
        assert validate.exit_code == 0

        dump = runner.invoke(codegen, ["--cases", str(suite_dir), "--dump-ir"])
        assert dump.exit_code == 0
        payload = json.loads(dump.output)
        case = payload["suites"][0]["files"][0]["cases"][0]
        assert {item["name"]: item["provider"] for item in case["profile_variables"]} == {
            "base_url": "env",
            "password": "value",
            "username": "env",
        }

        generate = runner.invoke(codegen, ["--cases", str(suite_dir)])
        assert generate.exit_code == 0
        generated = root / "test_workspace" / "tests" / "generated" / (
            "test_gateway_api_login_smoke_business.py"
        )
        text = generated.read_text(encoding="utf-8")
        assert "from aitest_kit.runtime_variables import resolve_profile_variables" in text
        assert "SUB2API_TEST_USER_EMAIL" in text
        assert "__tc_vars__[\"username\"]" in text
        assert "wrong-password" in text
        assert "os.environ" not in text


def test_codegen_cases_suite_inherits_module_case_flow_defaults(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        root = Path(cwd)
        fixture_dir = root / "test_workspace" / "tests" / "fixtures"
        fixture_dir.mkdir(parents=True, exist_ok=True)
        (fixture_dir / "codegen_profile_gateway_api.md").write_text(
            """```yaml
module_type: multi_endpoint
extra_imports:
  - "from test_workspace.tests.fixtures.gateway_api import setup_gateway_api"
default_fixture: setup_gateway_api
default_object: client_factory
default_case_setup:
  call: client_factory
  kwargs:
    case_id: "{case_id}"
  save_as: client
```
""",
            encoding="utf-8",
        )
        suite_dir = root / "test_workspace" / "casesuites" / "factory_smoke"
        suite_dir.mkdir(parents=True, exist_ok=True)
        (suite_dir / "aitest_suite.yaml").write_text(
            """module: gateway_api
suite: factory_smoke
case_files:
  - business.md
profile: codegen_profile_factory_smoke_suite.md
""",
            encoding="utf-8",
        )
        (suite_dir / "business.md").write_text(
            """# factory smoke

## 共享配置

**接口**：`GET /health`

---

## 一、冒烟

### TC-GW-061：factory health ok
- **优先级**：P0
- **断言**：`response.status == "ok"`
""",
            encoding="utf-8",
        )
        (suite_dir / "codegen_profile_factory_smoke_suite.md").write_text(
            """```yaml
profile_scope: case_suite
parent_module: gateway_api
suite: factory_smoke
case_flows:
  TC-GW-061:
    steps:
      - call: client.health
        save_as: resp
      - assert: 'assert resp["status"] == "ok"'
```
""",
            encoding="utf-8",
        )

        validate = runner.invoke(codegen, ["--cases", str(suite_dir), "--validate-profile"])
        assert validate.exit_code == 0
        assert "warnings=0" in validate.output

        dump = runner.invoke(codegen, ["--cases", str(suite_dir), "--dump-ir"])
        assert dump.exit_code == 0
        payload = json.loads(dump.output)
        case = payload["suites"][0]["files"][0]["cases"][0]
        assert case["fixtures"] == ["setup_gateway_api"]
        assert case["case_flow"]["object_name"] == "client_factory"
        assert case["case_flow"]["steps"][0]["call"] == "client_factory"
        assert case["case_flow"]["steps"][0]["kwargs"] == {"case_id": "TC-GW-061"}
        assert case["case_flow"]["steps"][1]["call"] == "client.health"


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
