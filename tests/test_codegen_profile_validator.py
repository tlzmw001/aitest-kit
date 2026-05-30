from __future__ import annotations

from pathlib import Path

import pytest

from aitest_kit.codegen.profile_validator import validate_profile_suite
from aitest_kit.codegen.project_config import ProjectConfig


def _write_target(
    root: Path,
    *,
    module_type: str = "standard_http",
    module_profile: str = "",
) -> Path:
    target_dir = root / "test_workspace" / "targets" / "sub2api"
    module_dir = target_dir / "modules"
    profile_dir = target_dir / "profiles"
    module_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "target.yaml").write_text(
        """target: sub2api
defaults:
  module_dir: test_workspace/targets/sub2api/modules
  fixture_dir: test_workspace/targets/sub2api/fixtures
  helper_dir: test_workspace/targets/sub2api/helpers
  profile_dir: test_workspace/targets/sub2api/profiles
  suite_dir: test_workspace/suites/sub2api
  generated_dir: test_workspace/generated/sub2api
  reports_dir: test_workspace/reports/sub2api
""",
        encoding="utf-8",
    )
    (module_dir / "gateway_api.yaml").write_text(
        f"""target: sub2api
module: gateway_api
module_type: {module_type}
fixture:
  file: gateway_api.py
  default_fixture: setup_gateway_api
profile:
  file: profile_gateway_api.md
""",
        encoding="utf-8",
    )
    (profile_dir / "profile_gateway_api.md").write_text(
        f"```yaml\n{module_profile}```\n",
        encoding="utf-8",
    )
    return profile_dir


def _write_suite(
    root: Path,
    *,
    case_id: str = "TC-GW-001",
    marker: str = "",
    suite_profile: str = "",
    with_base_request: bool = False,
) -> Path:
    suite_dir = root / "test_workspace" / "suites" / "sub2api" / "gateway_smoke"
    suite_dir.mkdir(parents=True, exist_ok=True)
    (suite_dir / "suite.yaml").write_text(
        """target: sub2api
module: gateway_api
suite: gateway_smoke
case_files:
  - business.md
profile: profile_gateway_smoke_suite.md
""",
        encoding="utf-8",
    )
    base_request = ""
    if with_base_request:
        base_request = """**基础请求体（HTTP）**：

```json
{"request_id": "req_demo"}
```
"""
    marker_line = f"- **标记**：`{marker}`\n" if marker else ""
    (suite_dir / "business.md").write_text(
        f"""# gateway smoke

## 共享配置

**通用断言**：`response.code == 0`
{base_request}
---

## 一、基础场景

### {case_id}：demo case
- **优先级**：P1
{marker_line}- **断言**：`response.code == 0`
""",
        encoding="utf-8",
    )
    (suite_dir / "profile_gateway_smoke_suite.md").write_text(
        f"```yaml\n{suite_profile}```\n",
        encoding="utf-8",
    )
    return suite_dir


def _project(module_type: str = "standard_http") -> ProjectConfig:
    return ProjectConfig(
        module_types={
            "standard_http": {"description": "standard"},
            "isolated_service": {"description": "isolated", "requires": ["case_bodies"]},
            module_type: {"description": module_type},
        },
    )


def test_validate_profile_suite_rejects_module_override(tmp_path):
    profile_dir = _write_target(tmp_path)
    suite_dir = _write_suite(tmp_path)

    with pytest.raises(ValueError):
        validate_profile_suite(suite_dir, module="gateway_api", profile_dir=profile_dir)


def test_profile_validator_rejects_conflict_and_naked_assert(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    profile_dir = _write_target(tmp_path)
    suite_dir = _write_suite(
        tmp_path,
        suite_profile="""profile_scope: case_suite
parent_module: gateway_api
suite: gateway_smoke
case_bodies:
  TC-GW-001: |
    assert True
case_flows:
  TC-GW-001:
    fixture: setup_gateway_api
    steps:
      - assert: "`resp == ERR`"
""",
    )

    report = validate_profile_suite(suite_dir, profile_dir=profile_dir, project=_project())

    messages = "\n".join(diag.message for diag in report.errors)
    assert "defined in both case_bodies and case_flows" in messages
    assert "must start with 'assert '" in messages


def test_profile_validator_rejects_unknown_case_reference(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    profile_dir = _write_target(tmp_path)
    suite_dir = _write_suite(
        tmp_path,
        suite_profile="""profile_scope: case_suite
parent_module: gateway_api
suite: gateway_smoke
request_overrides:
  TC-GW-999:
    user_id: u_missing
""",
    )

    report = validate_profile_suite(suite_dir, profile_dir=profile_dir, project=_project())

    assert any(diag.code == "E505" for diag in report.errors)
    assert any("does not exist in suite markdown cases" in diag.message for diag in report.errors)


def test_profile_validator_rejects_variables_with_unknown_case_reference(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    profile_dir = _write_target(tmp_path)
    suite_dir = _write_suite(
        tmp_path,
        suite_profile="""profile_scope: case_suite
parent_module: gateway_api
suite: gateway_smoke
variables:
  cases:
    TC-GW-999:
      username:
        env: DEMO_USER
""",
    )

    report = validate_profile_suite(suite_dir, profile_dir=profile_dir, project=_project())

    assert any(diag.code == "E505" for diag in report.errors)
    assert any("variables.cases.TC-GW-999" in diag.source for diag in report.errors)


def test_profile_validator_warns_feasibility_suspect_executable_case(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    profile_dir = _write_target(tmp_path)
    suite_dir = _write_suite(
        tmp_path,
        marker="[!可行性存疑: 需要外部账号]",
        suite_profile="""profile_scope: case_suite
parent_module: gateway_api
suite: gateway_smoke
case_flows:
  TC-GW-001:
    fixture: setup_gateway_api
    object: client
    steps:
      - assert: 'assert True'
""",
    )

    report = validate_profile_suite(suite_dir, profile_dir=profile_dir, project=_project())

    assert any(diag.code == "W503" for diag in report.warnings)


def test_profile_validator_allows_pure_manual_without_base_request_or_profile_entry(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    profile_dir = _write_target(tmp_path)
    suite_dir = _write_suite(
        tmp_path,
        marker="[manual]",
        suite_profile="""profile_scope: case_suite
parent_module: gateway_api
suite: gateway_smoke
""",
    )

    report = validate_profile_suite(suite_dir, profile_dir=profile_dir, project=_project())

    assert not any(diag.code == "E506" for diag in report.errors)


def test_profile_validator_warns_manual_comment_only_case_flow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    profile_dir = _write_target(tmp_path)
    suite_dir = _write_suite(
        tmp_path,
        marker="[manual]",
        suite_profile="""profile_scope: case_suite
parent_module: gateway_api
suite: gateway_smoke
case_flows:
  TC-GW-001:
    steps:
      - comment: 人工检查监控指标是否增加
""",
    )

    report = validate_profile_suite(suite_dir, profile_dir=profile_dir, project=_project())

    assert any(diag.code == "W505" for diag in report.warnings)
    assert not any(diag.code == "E527" for diag in report.errors)


def test_profile_validator_allows_semi_automated_manual_case_flow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    profile_dir = _write_target(tmp_path)
    suite_dir = _write_suite(
        tmp_path,
        marker="[manual]",
        suite_profile="""profile_scope: case_suite
parent_module: gateway_api
suite: gateway_smoke
case_flows:
  TC-GW-001:
    fixture: setup_gateway_api
    object: client
    steps:
      - call: client.trigger
        save_as: resp
      - comment: 人工检查监控指标是否增加
""",
    )

    report = validate_profile_suite(suite_dir, profile_dir=profile_dir, project=_project())

    assert not any(diag.code == "W505" for diag in report.warnings)
    assert report.errors == []


def test_profile_validator_rejects_non_manual_comment_only_case_flow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    profile_dir = _write_target(tmp_path)
    suite_dir = _write_suite(
        tmp_path,
        suite_profile="""profile_scope: case_suite
parent_module: gateway_api
suite: gateway_smoke
case_flows:
  TC-GW-001:
    steps:
      - comment: TODO 后续补真实调用
""",
    )

    report = validate_profile_suite(suite_dir, profile_dir=profile_dir, project=_project())

    assert any(diag.code == "E527" for diag in report.errors)


def test_profile_validator_warns_fixture_reinvocation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    profile_dir = _write_target(tmp_path)
    suite_dir = _write_suite(
        tmp_path,
        suite_profile="""profile_scope: case_suite
parent_module: gateway_api
suite: gateway_smoke
case_flows:
  TC-GW-001:
    fixture: setup_gateway_api
    object: client
    steps:
      - call: setup_gateway_api
        save_as: client
      - assert: 'assert True'
""",
    )

    report = validate_profile_suite(suite_dir, profile_dir=profile_dir, project=_project())

    assert any(diag.code == "W504" for diag in report.warnings)


def test_profile_validator_allows_case_flow_description_metadata(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    profile_dir = _write_target(tmp_path)
    suite_dir = _write_suite(
        tmp_path,
        suite_profile="""profile_scope: case_suite
parent_module: gateway_api
suite: gateway_smoke
case_flows:
  TC-GW-001:
    fixture: setup_gateway_api
    object: client
    description: login and query current user
    steps:
      - call: client.health
        save_as: resp
      - assert: 'assert resp.status_code == 200'
""",
    )

    report = validate_profile_suite(suite_dir, profile_dir=profile_dir, project=_project())

    assert report.errors == []


def test_profile_validator_rejects_suite_case_flow_in_module_profile(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    profile_dir = _write_target(
        tmp_path,
        module_profile="""module_type: standard_http
case_flows:
  TC-GW-001:
    fixture: setup_gateway_api
    object: client
    steps:
      - assert: 'assert True'
""",
    )
    suite_dir = _write_suite(
        tmp_path,
        suite_profile="""profile_scope: case_suite
parent_module: gateway_api
suite: gateway_smoke
""",
    )

    report = validate_profile_suite(suite_dir, profile_dir=profile_dir, project=_project())

    assert any(diag.code == "E526" for diag in report.errors)
    assert any("suite profile, not the module profile" in diag.message for diag in report.errors)
    assert any(diag.source == "case_flows" for diag in report.errors)


def test_profile_validator_rejects_suite_variables_cases_in_module_profile(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    profile_dir = _write_target(
        tmp_path,
        module_profile="""module_type: standard_http
variables:
  cases:
    TC-GW-001:
      token:
        env: DEMO_TOKEN
""",
    )
    suite_dir = _write_suite(
        tmp_path,
        with_base_request=True,
        suite_profile="""profile_scope: case_suite
parent_module: gateway_api
suite: gateway_smoke
""",
    )

    report = validate_profile_suite(suite_dir, profile_dir=profile_dir, project=_project())

    assert any(diag.code == "E526" for diag in report.errors)
    assert any(diag.source == "variables.cases" for diag in report.errors)


def test_profile_validator_allows_declared_fixture_factory_setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    profile_dir = _write_target(tmp_path)
    suite_dir = _write_suite(
        tmp_path,
        suite_profile="""profile_scope: case_suite
parent_module: gateway_api
suite: gateway_smoke
default_fixture: setup_gateway_api
default_object: client
default_case_setup:
  call: setup_gateway_api
  kwargs:
    case_id: "{case_id}"
  save_as: client
case_flows:
  TC-GW-001:
    steps:
      - assert: 'assert True'
""",
    )

    report = validate_profile_suite(suite_dir, profile_dir=profile_dir, project=_project())

    assert not any(diag.code == "W504" for diag in report.warnings)


def test_profile_validator_checks_module_type_from_module_yaml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    profile_dir = _write_target(tmp_path, module_type="isolated_service")
    suite_dir = _write_suite(
        tmp_path,
        with_base_request=True,
        suite_profile="""profile_scope: case_suite
parent_module: gateway_api
suite: gateway_smoke
""",
    )

    report = validate_profile_suite(
        suite_dir,
        profile_dir=profile_dir,
        project=ProjectConfig(
            module_types={
                "standard_http": {"description": "standard"},
                "isolated_service": {"description": "isolated", "requires": ["case_bodies"]},
            },
        ),
    )

    assert any(diag.code == "E504" for diag in report.errors)
    assert any("requires case_bodies or case_flows" in diag.message for diag in report.errors)
