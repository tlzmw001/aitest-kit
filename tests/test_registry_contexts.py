from __future__ import annotations

from pathlib import Path

from aitest_kit.registry import (
    load_module_context,
    load_suite_context,
    load_target_context,
    load_task_context,
)


def test_registry_loads_target_module_suite_and_task_with_external_paths(tmp_path, monkeypatch):
    workspace = tmp_path / "aitest_project"
    workspace.mkdir()
    knowledge = tmp_path / "company_knowledge" / "sub2api" / "knowledge"
    knowledge_l1 = knowledge / "L1"
    knowledge_l2 = knowledge / "L2"
    knowledge_l1.mkdir(parents=True)
    knowledge_l2.mkdir(parents=True)
    (knowledge / "L0_system_architecture.md").write_text("# L0\n", encoding="utf-8")
    (knowledge_l1 / "gateway_api.md").write_text("# gateway_api\n", encoding="utf-8")
    (knowledge_l2 / "quota_billing_v2.md").write_text("# quota\n", encoding="utf-8")

    monkeypatch.setenv("SUB2API_KNOWLEDGE", str(knowledge))

    target_dir = workspace / "test_workspace" / "targets" / "sub2api"
    (target_dir / "modules").mkdir(parents=True)
    (target_dir / "fixtures").mkdir()
    (target_dir / "profiles").mkdir()
    (target_dir / "target.yaml").write_text(
        """target: sub2api
source_root: /srv/sub2api
docs:
  - ${SUB2API_KNOWLEDGE}/L0_system_architecture.md
knowledge_refs:
  l0: ${SUB2API_KNOWLEDGE}/L0_system_architecture.md
defaults:
  fixture_dir: test_workspace/targets/sub2api/fixtures
  profile_dir: test_workspace/targets/sub2api/profiles
""",
        encoding="utf-8",
    )
    (target_dir / "modules" / "gateway_api.yaml").write_text(
        """target: sub2api
module: gateway_api
module_type: multi_endpoint
knowledge_refs:
  l1: ${SUB2API_KNOWLEDGE}/L1/gateway_api.md
fixture:
  file: gateway_api.py
  default_fixture: setup_gateway_api
registered_suites:
  - suite: quota_billing_v2
    manifest: external_suites/sub2api/quota_billing_v2/suite.yaml
    status: active
""",
        encoding="utf-8",
    )

    suite_dir = workspace / "external_suites" / "sub2api" / "quota_billing_v2"
    suite_dir.mkdir(parents=True)
    (suite_dir / "business.md").write_text("# business\n", encoding="utf-8")
    (suite_dir / "profile_quota_billing_v2_suite.md").write_text("# profile\n", encoding="utf-8")
    (suite_dir / "suite.yaml").write_text(
        """target: sub2api
module: gateway_api
suite: quota_billing_v2
case_files:
  - business.md
knowledge_refs:
  l2:
    - ${SUB2API_KNOWLEDGE}/L2/quota_billing_v2.md
""",
        encoding="utf-8",
    )

    task_dir = workspace / "test_workspace" / "tasks"
    task_dir.mkdir(parents=True)
    (task_dir / "sub2api.env").write_text("SUB2API_BASE_URL=http://127.0.0.1\n", encoding="utf-8")
    (task_dir / "release_regression.yaml").write_text(
        """schema_version: 1
name: release_regression
description: release regression suite
env_files:
  - sub2api.env
defaults:
  include_manual: false
  pytest_args:
    - -q
  allow_risk:
    - calls_upstream
units:
  - name: quota billing
    target: sub2api
    module: gateway_api
    suite: quota_billing_v2
    suite_file: ../../external_suites/sub2api/quota_billing_v2/suite.yaml
    case_ids:
      - TC-GW-041
    include_manual: true
    pytest_args:
      - -s
    allow_risk:
      - may_bill
""",
        encoding="utf-8",
    )

    target = load_target_context("sub2api", workspace_root=workspace)
    assert target.diagnostics == []
    assert target.target == "sub2api"
    assert target.knowledge_refs["l0"] == knowledge / "L0_system_architecture.md"
    assert target.docs == [knowledge / "L0_system_architecture.md"]
    assert target.defaults.profile_dir == target_dir / "profiles"

    module = load_module_context(target, "gateway_api")
    assert module.diagnostics == []
    assert module.module == "gateway_api"
    assert module.module_type == "multi_endpoint"
    assert module.knowledge_refs["l1"] == knowledge_l1 / "gateway_api.md"
    assert module.fixture_path == target_dir / "fixtures" / "gateway_api.py"
    assert module.default_fixture == "setup_gateway_api"
    assert module.profile_path == target_dir / "profiles" / "profile_gateway_api.md"
    assert module.registered_suites[0].manifest == suite_dir / "suite.yaml"

    suite = load_suite_context(suite_dir / "suite.yaml", workspace_root=workspace)
    assert suite.diagnostics == []
    assert suite.target == "sub2api"
    assert suite.module == "gateway_api"
    assert suite.suite == "quota_billing_v2"
    assert suite.case_files == [suite_dir / "business.md"]
    assert suite.profile_path == suite_dir / "profile_quota_billing_v2_suite.md"
    assert suite.knowledge_refs["l2"] == [knowledge_l2 / "quota_billing_v2.md"]

    task = load_task_context("test_workspace/tasks/release_regression.yaml", workspace_root=workspace)
    assert task.diagnostics == []
    assert task.task == "release_regression"
    assert task.description == "release regression suite"
    assert task.env_files == [task_dir / "sub2api.env"]
    assert task.defaults.include_manual is False
    assert task.defaults.pytest_args == ["-q"]
    assert task.defaults.allow_risk == ["calls_upstream"]
    assert task.units[0].name == "quota billing"
    assert task.units[0].target == "sub2api"
    assert task.units[0].module == "gateway_api"
    assert task.units[0].suite == "quota_billing_v2"
    assert task.units[0].suite_file == suite_dir / "suite.yaml"
    assert task.units[0].case_ids == ["TC-GW-041"]
    assert task.units[0].include_manual is True
    assert task.units[0].pytest_args == ["-s"]
    assert task.units[0].allow_risk == ["may_bill"]


def test_registry_loads_registered_suite_from_string_manifest(tmp_path):
    workspace, suite_file = _registry_workspace_with_suite(
        tmp_path,
        registered_suites=f"""registered_suites:
  - {suite_file_placeholder()}
""",
    )

    target = load_target_context("sub2api", workspace_root=workspace)
    module = load_module_context(target, "gateway_api")

    assert module.diagnostics == []
    assert module.registered_suites[0].suite == "quota_billing_v2"
    assert module.registered_suites[0].manifest == suite_file
    assert module.registered_suites[0].status == "active"


def test_registry_derives_registered_suite_name_from_mapping_manifest(tmp_path):
    workspace, suite_file = _registry_workspace_with_suite(
        tmp_path,
        registered_suites=f"""registered_suites:
  - manifest: {suite_file_placeholder()}
    status: paused
""",
    )

    target = load_target_context("sub2api", workspace_root=workspace)
    module = load_module_context(target, "gateway_api")

    assert module.diagnostics == []
    assert module.registered_suites[0].suite == "quota_billing_v2"
    assert module.registered_suites[0].manifest == suite_file
    assert module.registered_suites[0].status == "paused"


def test_registry_reports_registered_suite_name_mismatch(tmp_path):
    workspace, _ = _registry_workspace_with_suite(
        tmp_path,
        registered_suites=f"""registered_suites:
  - suite: wrong_suite
    manifest: {suite_file_placeholder()}
""",
    )

    target = load_target_context("sub2api", workspace_root=workspace)
    module = load_module_context(target, "gateway_api")

    assert any("does not match manifest suite quota_billing_v2" in diagnostic for diagnostic in module.diagnostics)


def test_registry_keeps_explicit_suite_even_if_manifest_is_created_later(tmp_path):
    workspace, _ = _registry_workspace_with_suite(
        tmp_path,
        registered_suites="""registered_suites:
  - suite: future_suite
    manifest: test_workspace/suites/sub2api/future_suite/suite.yaml
""",
    )

    target = load_target_context("sub2api", workspace_root=workspace)
    module = load_module_context(target, "gateway_api")

    assert module.diagnostics == []
    assert module.registered_suites[0].suite == "future_suite"
    assert module.registered_suites[0].manifest == (
        workspace / "test_workspace" / "suites" / "sub2api" / "future_suite" / "suite.yaml"
    )


def test_registry_loads_target_from_central_targets_yaml(tmp_path):
    workspace = tmp_path / "aitest_project"
    config_dir = workspace / "aitest_config"
    config_dir.mkdir(parents=True)
    (config_dir / "targets.yaml").write_text(
        """targets:
  coupon_system:
    target: coupon_system
    defaults:
      module_dir: test_workspace/targets/coupon_system/modules
      profile_dir: test_workspace/targets/coupon_system/profiles
    knowledge_refs:
      l0: test_workspace/knowledge/L0_system_architecture.md
""",
        encoding="utf-8",
    )

    context = load_target_context("coupon_system", workspace_root=workspace)

    assert context.diagnostics == []
    assert context.target == "coupon_system"
    assert context.config_path == config_dir / "targets.yaml"
    assert context.defaults.module_dir == workspace / "test_workspace" / "targets" / "coupon_system" / "modules"
    assert context.knowledge_refs["l0"] == workspace / "test_workspace" / "knowledge" / "L0_system_architecture.md"


def test_registry_loads_target_from_unified_aitest_yaml(tmp_path):
    workspace = tmp_path / "aitest_project"
    config_dir = workspace / "aitest_config"
    config_dir.mkdir(parents=True)
    (config_dir / "aitest.yaml").write_text(
        """targets:
  coupon_system:
    target: coupon_system
    defaults:
      module_dir: test_workspace/targets/coupon_system/modules
      profile_dir: test_workspace/targets/coupon_system/profiles
    knowledge_refs:
      l0: test_workspace/knowledge/L0_system_architecture.md
""",
        encoding="utf-8",
    )

    context = load_target_context("coupon_system", workspace_root=workspace)

    assert context.diagnostics == []
    assert context.target == "coupon_system"
    assert context.config_path == config_dir / "aitest.yaml"
    assert context.defaults.module_dir == workspace / "test_workspace" / "targets" / "coupon_system" / "modules"
    assert context.knowledge_refs["l0"] == workspace / "test_workspace" / "knowledge" / "L0_system_architecture.md"


def test_registry_reports_missing_environment_reference(tmp_path):
    workspace = tmp_path / "aitest_project"
    target_dir = workspace / "test_workspace" / "targets" / "sub2api"
    target_dir.mkdir(parents=True)
    (target_dir / "target.yaml").write_text(
        """target: sub2api
knowledge_refs:
  l0: ${MISSING_KNOWLEDGE_ROOT}/L0_system_architecture.md
""",
        encoding="utf-8",
    )

    context = load_target_context("sub2api", workspace_root=workspace)

    assert any("MISSING_KNOWLEDGE_ROOT" in diagnostic for diagnostic in context.diagnostics)


def test_registry_loads_suite_yaml_manifest(tmp_path):
    workspace = tmp_path / "aitest_project"
    suite_dir = tmp_path / "external_suite"
    suite_dir.mkdir()
    (suite_dir / "business.md").write_text("# business\n", encoding="utf-8")
    (suite_dir / "profile_smoke_suite.md").write_text("# profile\n", encoding="utf-8")
    (suite_dir / "suite.yaml").write_text(
        """target: coupon_system
module: calibration
suite: smoke
case_files:
  - business.md
""",
        encoding="utf-8",
    )

    context = load_suite_context(suite_dir, workspace_root=workspace)

    assert context.diagnostics == []
    assert context.manifest_path == suite_dir / "suite.yaml"
    assert context.profile_path == suite_dir / "profile_smoke_suite.md"
    assert context.case_files == [suite_dir / "business.md"]


def test_registry_rejects_module_profile_field(tmp_path):
    workspace, _ = _registry_workspace_with_suite(tmp_path, registered_suites="registered_suites: []\n")
    module_file = (
        workspace / "test_workspace" / "targets" / "sub2api" / "modules" / "gateway_api.yaml"
    )
    module_file.write_text(
        """target: sub2api
module: gateway_api
module_type: multi_endpoint
fixture:
  file: gateway_api.py
  default_fixture: setup_gateway_api
profile:
  file: profile_gateway_api.md
registered_suites: []
""",
        encoding="utf-8",
    )

    target = load_target_context("sub2api", workspace_root=workspace)
    module = load_module_context(target, "gateway_api")

    assert any("module.yaml must not contain profile" in diagnostic for diagnostic in module.diagnostics)
    assert module.profile_path == (
        workspace / "test_workspace" / "targets" / "sub2api" / "profiles" / "profile_gateway_api.md"
    )


def test_registry_rejects_suite_manifest_profile_field(tmp_path):
    workspace, suite_file = _registry_workspace_with_suite(
        tmp_path,
        registered_suites=f"""registered_suites:
  - {suite_file_placeholder()}
""",
    )
    suite_file.write_text(
        """target: sub2api
module: gateway_api
suite: quota_billing_v2
case_files:
  - business.md
profile: profile_quota_billing_v2_suite.md
""",
        encoding="utf-8",
    )

    suite = load_suite_context(suite_file, workspace_root=workspace)

    assert any(
        "suite manifest must not contain generation or execution fields: profile" in diagnostic
        for diagnostic in suite.diagnostics
    )
    assert suite.profile_path == suite_file.parent / "profile_quota_billing_v2_suite.md"


def suite_file_placeholder() -> str:
    return "test_workspace/suites/sub2api/quota_billing_v2/suite.yaml"


def _registry_workspace_with_suite(tmp_path, *, registered_suites: str):
    workspace = tmp_path / "aitest_project"
    target_dir = workspace / "test_workspace" / "targets" / "sub2api"
    (target_dir / "modules").mkdir(parents=True)
    (target_dir / "fixtures").mkdir()
    (target_dir / "profiles").mkdir()
    (target_dir / "target.yaml").write_text(
        """target: sub2api
defaults:
  module_dir: test_workspace/targets/sub2api/modules
  fixture_dir: test_workspace/targets/sub2api/fixtures
  profile_dir: test_workspace/targets/sub2api/profiles
  suite_dir: test_workspace/suites/sub2api
  generated_dir: test_workspace/generated/sub2api
  reports_dir: test_workspace/reports/sub2api
""",
        encoding="utf-8",
    )
    (target_dir / "modules" / "gateway_api.yaml").write_text(
        f"""target: sub2api
module: gateway_api
module_type: multi_endpoint
fixture:
  file: gateway_api.py
  default_fixture: setup_gateway_api
{registered_suites}""",
        encoding="utf-8",
    )

    suite_dir = workspace / "test_workspace" / "suites" / "sub2api" / "quota_billing_v2"
    suite_dir.mkdir(parents=True)
    (suite_dir / "business.md").write_text("# business\n", encoding="utf-8")
    (suite_dir / "profile_quota_billing_v2_suite.md").write_text("# profile\n", encoding="utf-8")
    suite_file = suite_dir / "suite.yaml"
    suite_file.write_text(
        """target: sub2api
module: gateway_api
suite: quota_billing_v2
case_files:
  - business.md
""",
        encoding="utf-8",
    )
    return workspace, suite_file
