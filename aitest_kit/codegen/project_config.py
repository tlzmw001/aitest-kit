"""Project-level codegen config schema and loader.

This module is not the project configuration edit point. Project-specific
codegen configuration should live in aitest_config/project_config.yaml.

The fallback data below is only for compatibility when that YAML file is
missing or omits optional fields; it is not the source of truth for this
repository's active project configuration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AssertionRule:
    pattern: str = ""
    template: str = ""
    regex: str = ""
    extract_vars: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    name: str = ""


@dataclass
class ProjectConfig:
    helper_import: str = "from test_workspace.tests.helpers import http as http_helper"
    api_path: str = "/api/v1/recommend"
    helper_call: str = "http_helper.post"
    grpc_helper_import: str = "from test_workspace.tests.helpers import grpc_ops"
    grpc_helper_call: str = "grpc_ops.recommend"
    var_map: dict[str, str] = field(default_factory=dict)
    module_abbrevs: dict[str, str] = field(default_factory=dict)
    builtin_assertion_rules: list[AssertionRule] = field(default_factory=list)
    named_templates: set[str] = field(default_factory=set)
    module_types: dict[str, dict[str, Any]] = field(default_factory=dict)


FALLBACK_PROJECT_CONFIG_DATA: dict[str, Any] = {
    "helper_import": "from test_workspace.tests.helpers import http as http_helper",
    "grpc_helper_import": "from test_workspace.tests.helpers import grpc_ops",
    "api_path": "/api/v1/recommend",
    "helper_call": "http_helper.post",
    "grpc_helper_call": "grpc_ops.recommend",
    "var_map": {
        "s": 'resp["results"][0]["score"]',
        "cal": 'resp["results"][0]["calibrated_score"]',
    },
    "module_abbrevs": {
        "calibration": "cal",
        "ab_experiment": "ab",
        "ab_service": "abs",
        "feature_scoring": "feat",
        "issuance": "issue",
        "logging": "log",
        "rough_ranking": "rank",
        "scene_routing": "route",
        "validation_ratelimit": "val",
        "e2e": "e2e",
    },
    "named_templates": ["piecewise_cascade", "piecewise_only", "skip"],
    "module_types": {
        "standard_recommend": {"description": "标准推荐接口模块"},
        "multi_endpoint": {"description": "多端点服务模块", "requires": ["case_bodies"]},
        "subprocess_capture": {"description": "需要隔离进程捕获输出", "requires": ["case_bodies"]},
        "isolated_service": {"description": "需要隔离服务实例", "requires": ["case_bodies"]},
    },
    "builtin_assertion_rules": [
        {
            "name": "status_code",
            "regex": r"^response\.(?:body\.)?code\s*==\s*(?P<value>\d+)",
            "template": 'assert resp["code"] == {value}',
        },
        {
            "name": "http_status_code",
            "regex": r"^response\.status_code\s*==\s*(?P<value>\d+)",
            "template": "assert resp.status_code == {value}",
        },
        {
            "name": "http_status_code_short",
            "regex": r"^status_code\s*==\s*(?P<value>\d+)",
            "template": "assert resp.status_code == {value}",
        },
        {
            "name": "full_body",
            "regex": r"^response\.body\s*==\s*(?P<value>.+)",
            "template": "assert resp == {value}",
        },
        {
            "name": "coupon_null",
            "regex": r"^(?:response\.body\.)?coupon\s*==\s*null$",
            "template": 'assert resp["coupon"] is None',
        },
        {
            "name": "coupon_top",
            "regex": r"^(?=.*coupon\.item_id)(?=.*top_result).*$",
            "template": 'assert resp["coupon"]["item_id"] == max(resp["results"], key=lambda r: r["score"])["item_id"]',
        },
        {
            "name": "coupon_top_max",
            "regex": r"^(?=.*coupon)(?=.*item_id)(?=.*max).*$",
            "template": 'assert resp["coupon"]["item_id"] == max(resp["results"], key=lambda r: r["score"])["item_id"]',
        },
        {
            "name": "set_match",
            "regex": r"^set\(response\.(?P<path>.+?)\)\s*==\s*(?P<expected>\{.+\})$",
            "template": "assert {result_set:path} == {expected}",
        },
        {
            "name": "length",
            "regex": r"^len\((?P<expr>.+?)\)\s*==\s*(?P<n>\d+)$",
            "template": "assert len({expr}) == {n}",
        },
        {
            "name": "linear_cal_with_b",
            "regex": r"^cal\s*==\s*round\(clamp\((?P<k>[0-9.]+)\s*\*\s*s\s*\+\s*(?P<b>[0-9.]+)\)\s*,\s*4\)",
            "template": "assert cal == pytest.approx(max(0, min(1, {k} * s + {b})), abs=1e-4)",
        },
        {
            "name": "linear_cal_no_b",
            "regex": r"^cal\s*==\s*round\(clamp\((?P<k>[0-9.]+)\s*\*\s*s\)\s*,\s*4\)",
            "template": "assert cal == pytest.approx(max(0, min(1, {k} * s)), abs=1e-4)",
        },
        {
            "name": "no_cal",
            "regex": r"^cal\s*==\s*s\b.*$",
            "template": "assert cal == pytest.approx(s)",
        },
        {
            "name": "comparison",
            "regex": r"^response\.(?:body\.)?(?P<path>\S+)\s*(?P<op>>=|<=|>|<)\s*(?P<value>.+)$",
            "template": "assert {response_path:path} {op} {value}",
        },
        {
            "name": "field_equality",
            "regex": r"^response\.(?:body\.)?(?P<path>\S+)\s*==\s*(?P<value>.+)$",
            "template": "assert {response_path:path} == {value}",
        },
    ],
}


def _rules_from(raw_rules: Any) -> list[AssertionRule]:
    if not isinstance(raw_rules, list):
        return []
    rules: list[AssertionRule] = []
    for item in raw_rules:
        if not isinstance(item, dict):
            continue
        rules.append(AssertionRule(
            pattern=item.get("pattern", "") or "",
            template=item.get("template", "") or "",
            regex=item.get("regex", "") or "",
            extract_vars=item.get("extract_vars", []) or [],
            params=item.get("params", {}) or {},
            name=item.get("name", "") or "",
        ))
    return rules


def _project_from(data: dict[str, Any]) -> ProjectConfig:
    return ProjectConfig(
        helper_import=data.get("helper_import", FALLBACK_PROJECT_CONFIG_DATA["helper_import"]),
        api_path=data.get("api_path", FALLBACK_PROJECT_CONFIG_DATA["api_path"]),
        helper_call=data.get("helper_call", FALLBACK_PROJECT_CONFIG_DATA["helper_call"]),
        grpc_helper_import=data.get("grpc_helper_import", FALLBACK_PROJECT_CONFIG_DATA["grpc_helper_import"]),
        grpc_helper_call=data.get("grpc_helper_call", FALLBACK_PROJECT_CONFIG_DATA["grpc_helper_call"]),
        var_map=dict(data.get("var_map") or FALLBACK_PROJECT_CONFIG_DATA["var_map"]),
        module_abbrevs=dict(data.get("module_abbrevs") or FALLBACK_PROJECT_CONFIG_DATA["module_abbrevs"]),
        builtin_assertion_rules=_rules_from(data.get("builtin_assertion_rules")),
        named_templates=set(data.get("named_templates") or FALLBACK_PROJECT_CONFIG_DATA["named_templates"]),
        module_types=dict(data.get("module_types") or FALLBACK_PROJECT_CONFIG_DATA["module_types"]),
    )


def fallback_project_config() -> ProjectConfig:
    return _project_from(FALLBACK_PROJECT_CONFIG_DATA)


def load_project_config(path: str | Path = "aitest_config/project_config.yaml") -> ProjectConfig:
    config_path = Path(path)
    if not config_path.exists():
        return fallback_project_config()

    try:
        import yaml
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"无法读取项目 codegen 配置 {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise RuntimeError(f"项目 codegen 配置 {config_path} 必须是 YAML mapping")

    return _project_from({**FALLBACK_PROJECT_CONFIG_DATA, **raw})


DEFAULT_PROJECT = load_project_config()
