from __future__ import annotations

from pathlib import Path

from aitest_kit.codegen.project_config import load_project_config
from aitest_kit.workspace_config import load_workspace_paths


def test_workspace_paths_require_aitest_yaml_for_custom_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / "aitest_config"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(
        """paths:
  cases_dir: cases
  generated_dir: generated
  fixtures_dir: fixtures
  reports_dir: reports
  project_config: aitest_config/project_config.yaml
""",
        encoding="utf-8",
    )

    paths = load_workspace_paths()

    assert paths.generated_dir == Path("test_workspace/generated")
    assert paths.profile_dir == Path("test_workspace/targets")
    assert paths.reports_dir == Path("test_workspace/reports")
    assert paths.project_config == Path("aitest_config/aitest.yaml")


def test_workspace_paths_load_aitest_yaml_aliases(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / "aitest_config"
    config_dir.mkdir()
    (config_dir / "aitest.yaml").write_text(
        """workspace:
  paths:
    generated_dir: generated
    profile_dir: profiles
    reports_dir: reports
""",
        encoding="utf-8",
    )

    paths = load_workspace_paths()

    assert paths.generated_dir == Path("generated")
    assert paths.profile_dir == Path("profiles")
    assert paths.reports_dir == Path("reports")


def test_project_config_loads_codegen_section_from_aitest_yaml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / "aitest_config"
    config_dir.mkdir()
    (config_dir / "aitest.yaml").write_text(
        """codegen:
  helper_import: "from custom.helpers import http as http_helper"
  api_path: /custom
  module_types:
    standard_http:
      description: standard HTTP module
""",
        encoding="utf-8",
    )

    project = load_project_config()

    assert project.helper_import == "from custom.helpers import http as http_helper"
    assert project.api_path == "/custom"
    assert project.module_types == {"standard_http": {"description": "standard HTTP module"}}


def test_project_config_fallback_is_generic_when_aitest_yaml_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    project = load_project_config()

    assert project.api_path == "/api/v1/replace-me"
    assert project.var_map == {}
    assert project.module_abbrevs == {}
    assert "standard_recommend" not in project.module_types
    assert {rule.name for rule in project.builtin_assertion_rules}.isdisjoint(
        {"coupon_null", "coupon_top", "coupon_top_max", "linear_cal_with_b", "linear_cal_no_b", "no_cal"}
    )


def test_project_config_preserves_explicit_empty_codegen_maps(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / "aitest_config"
    config_dir.mkdir()
    (config_dir / "aitest.yaml").write_text(
        """codegen:
  var_map: {}
  module_abbrevs: {}
  module_types: {}
""",
        encoding="utf-8",
    )

    project = load_project_config()

    assert project.var_map == {}
    assert project.module_abbrevs == {}
    assert project.module_types == {}
