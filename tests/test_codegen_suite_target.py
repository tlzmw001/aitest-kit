from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from aitest_kit.codegen.cli import codegen
from aitest_kit.codegen.suite import load_suite_context_for_paths


def _write_module_profile(root: Path) -> None:
    target_dir = root / "test_workspace" / "targets" / "sub2api"
    profile_dir = target_dir / "profiles"
    profile_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "target.yaml").write_text(
        """target: sub2api
defaults:
  profile_dir: test_workspace/targets/sub2api/profiles
  generated_dir: test_workspace/generated/sub2api
  reports_dir: test_workspace/reports/sub2api
""",
        encoding="utf-8",
    )
    (profile_dir / "profile_gateway_api.md").write_text(
        """```yaml
module_type: multi_endpoint
extra_imports:
  - "from test_workspace.targets.sub2api.fixtures.gateway_api import setup_gateway_api"
default_fixture: setup_gateway_api
default_object: client
```
""",
        encoding="utf-8",
    )


def _write_suite(root: Path, *, profile_name: str = "profile_quota_billing_v2_suite.md") -> Path:
    suite_dir = root / "test_workspace" / "suites" / "sub2api" / "quota_billing_v2"
    suite_dir.mkdir(parents=True, exist_ok=True)
    (suite_dir / "quota_billing_business.md").write_text(
        """# quota billing cases

## 共享配置

**接口**：`GET /health`

---

## 一、冒烟

### TC-GW-041：health ok
- **优先级**：P0
- **断言**：`response.status == "ok"`
""",
        encoding="utf-8",
    )
    (suite_dir / profile_name).write_text(
        """```yaml
profile_scope: case_suite
parent_module: gateway_api
suite: quota_billing_v2
case_flows:
  TC-GW-041:
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


def test_suite_file_uses_target_defaults_for_profile_and_generated_dir(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        root = Path(cwd)
        target_dir = root / "test_workspace" / "targets" / "sub2api"
        profile_dir = target_dir / "profiles"
        profile_dir.mkdir(parents=True)
        (target_dir / "target.yaml").write_text(
            """target: sub2api
defaults:
  profile_dir: test_workspace/targets/sub2api/profiles
  generated_dir: test_workspace/generated/sub2api
  reports_dir: test_workspace/reports/sub2api
""",
            encoding="utf-8",
        )
        (profile_dir / "profile_gateway_api.md").write_text(
            """```yaml
module_type: multi_endpoint
extra_imports:
  - "from test_workspace.targets.sub2api.fixtures.gateway_api import setup_gateway_api"
default_fixture: setup_gateway_api
default_object: client
```
""",
            encoding="utf-8",
        )
        suite_dir = _write_suite(root)
        suite_file = suite_dir / "suite.yaml"
        suite_file.write_text(
            """target: sub2api
module: gateway_api
suite: quota_billing_v2
case_files:
  - quota_billing_business.md
""",
            encoding="utf-8",
        )

        context = load_suite_context_for_paths(suite_file)
        assert context.module_profile_path == profile_dir / "profile_gateway_api.md"

        generate = runner.invoke(codegen, ["--suite-file", str(suite_file)])
        assert generate.exit_code == 0, generate.output
        generated = root / "test_workspace" / "generated" / "sub2api" / (
            "test_gateway_api_quota_billing_v2_quota_billing_business.py"
        )
        old_generated = root / "test_workspace" / "tests" / "generated" / (
            "test_gateway_api_quota_billing_v2_quota_billing_business.py"
        )
        assert generated.exists()
        assert not old_generated.exists()


def test_suite_file_auto_imports_target_module_fixture(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        root = Path(cwd)
        target_dir = root / "test_workspace" / "targets" / "sub2api"
        profile_dir = target_dir / "profiles"
        fixture_dir = target_dir / "fixtures"
        helper_dir = target_dir / "helpers"
        module_dir = target_dir / "modules"
        profile_dir.mkdir(parents=True)
        fixture_dir.mkdir()
        helper_dir.mkdir()
        module_dir.mkdir()
        (target_dir / "target.yaml").write_text(
            """target: sub2api
defaults:
  module_dir: test_workspace/targets/sub2api/modules
  fixture_dir: test_workspace/targets/sub2api/fixtures
  profile_dir: test_workspace/targets/sub2api/profiles
  generated_dir: test_workspace/generated/sub2api
""",
            encoding="utf-8",
        )
        (module_dir / "gateway_api.yaml").write_text(
            """target: sub2api
module: gateway_api
module_type: multi_endpoint
fixture:
  file: gateway_api.py
  default_fixture: setup_gateway_api
""",
            encoding="utf-8",
        )
        (fixture_dir / "gateway_api.py").write_text(
            """import pytest


@pytest.fixture
def setup_gateway_api():
    return object()
""",
            encoding="utf-8",
        )
        (helper_dir / "http.py").write_text(
            "def post(*args, **kwargs):\n    raise NotImplementedError\n",
            encoding="utf-8",
        )
        (profile_dir / "profile_gateway_api.md").write_text(
            """```yaml
default_fixture: setup_gateway_api
```
""",
            encoding="utf-8",
        )
        suite_dir = _write_suite(root)
        suite_file = suite_dir / "suite.yaml"
        suite_file.write_text(
            """target: sub2api
module: gateway_api
suite: quota_billing_v2
case_files:
  - quota_billing_business.md
""",
            encoding="utf-8",
        )

        generate = runner.invoke(codegen, ["--suite-file", str(suite_file)])

        assert generate.exit_code == 0, generate.output
        generated = root / "test_workspace" / "generated" / "sub2api" / (
            "test_gateway_api_quota_billing_v2_quota_billing_business.py"
        )
        assert generated.exists()
        context = load_suite_context_for_paths(suite_file)
        assert context.runtime_profile.data["module_type"] == "multi_endpoint"
        text = generated.read_text(encoding="utf-8")
        assert (
            "from test_workspace.targets.sub2api.fixtures.gateway_api import setup_gateway_api"
            in text
        )
        assert "from test_workspace.targets.sub2api.helpers import http as http_helper" in text


def test_codegen_cases_suite_profile_variables_render_runtime_lookup(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        root = Path(cwd)
        _write_module_profile(root)
        suite_dir = root / "test_workspace" / "suites" / "sub2api" / "login_smoke"
        suite_dir.mkdir(parents=True, exist_ok=True)
        (suite_dir / "suite.yaml").write_text(
            """target: sub2api
module: gateway_api
suite: login_smoke
case_files:
  - business.md
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
        (suite_dir / "profile_login_smoke_suite.md").write_text(
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

        validate = runner.invoke(codegen, ["--suite-file", str(suite_dir / "suite.yaml"), "--validate-profile"])
        assert validate.exit_code == 0

        dump = runner.invoke(codegen, ["--suite-file", str(suite_dir / "suite.yaml"), "--dump-ir"])
        assert dump.exit_code == 0
        payload = json.loads(dump.output)
        case = payload["suites"][0]["files"][0]["cases"][0]
        assert {item["name"]: item["provider"] for item in case["profile_variables"]} == {
            "base_url": "env",
            "password": "value",
            "username": "env",
        }

        generate = runner.invoke(codegen, ["--suite-file", str(suite_dir / "suite.yaml")])
        assert generate.exit_code == 0
        generated = root / "test_workspace" / "generated" / "sub2api" / (
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
        target_dir = root / "test_workspace" / "targets" / "sub2api"
        profile_dir = target_dir / "profiles"
        profile_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "target.yaml").write_text(
            """target: sub2api
defaults:
  profile_dir: test_workspace/targets/sub2api/profiles
  generated_dir: test_workspace/generated/sub2api
  reports_dir: test_workspace/reports/sub2api
""",
            encoding="utf-8",
        )
        (profile_dir / "profile_gateway_api.md").write_text(
            """```yaml
module_type: multi_endpoint
extra_imports:
  - "from test_workspace.targets.sub2api.fixtures.gateway_api import setup_gateway_api"
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
        suite_dir = root / "test_workspace" / "suites" / "sub2api" / "factory_smoke"
        suite_dir.mkdir(parents=True, exist_ok=True)
        (suite_dir / "suite.yaml").write_text(
            """target: sub2api
module: gateway_api
suite: factory_smoke
case_files:
  - business.md
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
        (suite_dir / "profile_factory_smoke_suite.md").write_text(
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

        validate = runner.invoke(codegen, ["--suite-file", str(suite_dir / "suite.yaml"), "--validate-profile"])
        assert validate.exit_code == 0
        assert "warnings=0" in validate.output

        dump = runner.invoke(codegen, ["--suite-file", str(suite_dir / "suite.yaml"), "--dump-ir"])
        assert dump.exit_code == 0
        payload = json.loads(dump.output)
        case = payload["suites"][0]["files"][0]["cases"][0]
        assert case["fixtures"] == ["setup_gateway_api"]
        assert case["case_flow"]["object_name"] == "client_factory"
        assert case["case_flow"]["steps"][0]["call"] == "client_factory"
        assert case["case_flow"]["steps"][0]["kwargs"] == {"case_id": "TC-GW-061"}
        assert case["case_flow"]["steps"][1]["call"] == "client.health"
