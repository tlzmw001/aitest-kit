"""Load module-level codegen profile settings."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from aitest_kit.codegen.project_config import AssertionRule


def load_profile_yaml(profile_path: str | Path) -> dict[str, Any]:
    """Extract the first YAML block from a codegen_profile."""
    path = Path(profile_path)
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    m = re.search(r"```ya?ml\s*\n(.*?)```", text, re.DOTALL)
    if not m:
        return {}

    try:
        import yaml
        data = yaml.safe_load(m.group(1))
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def load_profile_rules(profile_path: str | Path) -> list[AssertionRule]:
    """Extract assertion_rules from a codegen_profile's YAML block."""
    data = load_profile_yaml(profile_path)
    if not data:
        return []

    rules: list[AssertionRule] = []
    for item in data.get("assertion_rules", []):
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


def load_profile_request_overrides(profile_path: str | Path) -> dict[str, dict[str, Any]]:
    """Extract explicit case-level request overrides from a profile YAML block."""
    data = load_profile_yaml(profile_path)
    raw = data.get("request_overrides", {})
    if not isinstance(raw, dict):
        return {}

    result: dict[str, dict[str, Any]] = {}
    for case_id, overrides in raw.items():
        if isinstance(case_id, str) and isinstance(overrides, dict):
            result[case_id] = dict(overrides)
    return result


def load_profile_extra_imports(profile_path: str | Path) -> list[str]:
    """Extract extra import lines from a profile YAML block."""
    data = load_profile_yaml(profile_path)
    raw = data.get("extra_imports", [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str) and item.strip()]


def load_profile_case_fixtures(profile_path: str | Path) -> dict[str, list[str]]:
    """Extract per-case fixture signatures from a profile YAML block."""
    data = load_profile_yaml(profile_path)
    raw = data.get("case_fixtures", {})
    if not isinstance(raw, dict):
        return {}

    result: dict[str, list[str]] = {}
    for case_id, fixtures in raw.items():
        if not isinstance(case_id, str) or not isinstance(fixtures, list):
            continue
        result[case_id] = [
            item for item in fixtures
            if isinstance(item, str) and item.strip()
        ]
    return result


def load_profile_case_bodies(profile_path: str | Path) -> dict[str, list[str]]:
    """Extract per-case test body lines from a profile YAML block."""
    data = load_profile_yaml(profile_path)
    raw = data.get("case_bodies", {})
    if not isinstance(raw, dict):
        return {}

    result: dict[str, list[str]] = {}
    for case_id, body in raw.items():
        if not isinstance(case_id, str):
            continue
        if isinstance(body, str):
            result[case_id] = body.splitlines()
        elif isinstance(body, list):
            result[case_id] = [
                item for item in body
                if isinstance(item, str)
            ]
    return result


def load_profile_module_type(profile_path: str | Path) -> str | None:
    """Extract optional module_type from a profile YAML block."""
    data = load_profile_yaml(profile_path)
    module_type = data.get("module_type")
    return module_type if isinstance(module_type, str) and module_type.strip() else None
