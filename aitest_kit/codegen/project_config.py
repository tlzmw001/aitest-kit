"""Project-level codegen config schema and loader.

This module is not the project configuration edit point. Project-specific
codegen configuration should live in ``aitest_config/aitest.yaml``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aitest_kit.workspace_config import load_codegen_config_data


@dataclass
class AssertionRule:
    pattern: str = ""
    template: str = ""
    regex: str = ""
    extract_vars: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    name: str = ""


@dataclass
class DefaultRequestConfig:
    auto_fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectConfig:
    helper_import: str = "from aitest_kit.helpers import http as http_helper"
    api_path: str = "/api/v1/replace-me"
    helper_call: str = "http_helper.post"
    var_map: dict[str, str] = field(default_factory=dict)
    module_abbrevs: dict[str, str] = field(default_factory=dict)
    builtin_assertion_rules: list[AssertionRule] = field(default_factory=list)
    module_types: dict[str, dict[str, Any]] = field(default_factory=dict)
    default_request: DefaultRequestConfig = field(default_factory=DefaultRequestConfig)


FALLBACK_PROJECT_CONFIG_DATA: dict[str, Any] = {
    "helper_import": "from aitest_kit.helpers import http as http_helper",
    "api_path": "/api/v1/replace-me",
    "helper_call": "http_helper.post",
    "var_map": {},
    "module_abbrevs": {},
    "module_types": {
        "standard_http": {"description": "默认单接口 HTTP 模块"},
        "multi_endpoint": {"description": "多端点或自定义流程模块", "requires": ["case_bodies"]},
        "isolated_service": {"description": "需要隔离服务/运行时控制的模块", "requires": ["case_bodies"]},
    },
    "default_request": {
        "auto_fields": {},
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


def _default_request_from(raw: Any) -> DefaultRequestConfig:
    if not isinstance(raw, dict):
        return DefaultRequestConfig()
    auto_fields = raw.get("auto_fields", {})
    if not isinstance(auto_fields, dict):
        auto_fields = {}
    return DefaultRequestConfig(auto_fields=dict(auto_fields))


def _project_from(data: dict[str, Any]) -> ProjectConfig:
    var_map = data["var_map"] if isinstance(data.get("var_map"), dict) else FALLBACK_PROJECT_CONFIG_DATA["var_map"]
    module_abbrevs = (
        data["module_abbrevs"]
        if isinstance(data.get("module_abbrevs"), dict)
        else FALLBACK_PROJECT_CONFIG_DATA["module_abbrevs"]
    )
    module_types = (
        data["module_types"]
        if isinstance(data.get("module_types"), dict)
        else FALLBACK_PROJECT_CONFIG_DATA["module_types"]
    )
    return ProjectConfig(
        helper_import=data.get("helper_import", FALLBACK_PROJECT_CONFIG_DATA["helper_import"]),
        api_path=data.get("api_path", FALLBACK_PROJECT_CONFIG_DATA["api_path"]),
        helper_call=data.get("helper_call", FALLBACK_PROJECT_CONFIG_DATA["helper_call"]),
        var_map=dict(var_map),
        module_abbrevs=dict(module_abbrevs),
        builtin_assertion_rules=_rules_from(data.get("builtin_assertion_rules")),
        module_types=dict(module_types),
        default_request=_default_request_from(data.get("default_request")),
    )


def fallback_project_config() -> ProjectConfig:
    return _project_from(FALLBACK_PROJECT_CONFIG_DATA)


def load_project_config(path: str | Path = "aitest_config/aitest.yaml") -> ProjectConfig:
    raw = load_codegen_config_data(path)
    if raw is None:
        return fallback_project_config()

    if not isinstance(raw, dict):
        raise RuntimeError(f"项目 codegen 配置 {path} 必须是 YAML mapping")

    return _project_from({**FALLBACK_PROJECT_CONFIG_DATA, **raw})


DEFAULT_PROJECT = load_project_config()
