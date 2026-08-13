"""Resolved runtime view for codegen profiles."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aitest_kit.codegen.profile import (
    ProfileSource,
    RuntimeProfile,
    load_profile_case_bodies,
    load_profile_case_flows,
    load_profile_extra_imports,
    load_profile_module_type,
    load_profile_requests,
    load_profile_rules,
    load_profile_structured_assertions,
    load_profile_yaml,
)
from aitest_kit.codegen.profile_variables import load_profile_variables
from aitest_kit.codegen.project_config import AssertionRule
from aitest_kit.registry.models import ModuleBinding


@dataclass(frozen=True)
class ResolvedProfile:
    """Read-only runtime profile sections consumed by codegen."""

    raw: dict[str, Any]
    rules: list[AssertionRule]
    requests: dict[str, dict[str, Any]]
    structured_assertions: dict[str, list[dict[str, Any]]]
    extra_imports: list[str]
    case_bodies: dict[str, list[str]]
    case_flows: dict[str, dict[str, Any]]
    variables: dict[str, Any]
    module_type: str | None
    module_binding: ModuleBinding | None


def resolve_profile(profile: ProfileSource) -> ResolvedProfile:
    """Resolve profile data into the runtime sections used by codegen."""
    profile_source = profile or None
    raw = load_profile_yaml(profile_source)
    return ResolvedProfile(
        raw=raw,
        rules=load_profile_rules(profile_source),
        requests=load_profile_requests(profile_source),
        structured_assertions=load_profile_structured_assertions(profile_source),
        extra_imports=load_profile_extra_imports(profile_source),
        case_bodies=load_profile_case_bodies(profile_source),
        case_flows=load_profile_case_flows(profile_source),
        variables=load_profile_variables(raw),
        module_type=load_profile_module_type(profile_source),
        module_binding=(
            profile_source.module_binding
            if isinstance(profile_source, RuntimeProfile)
            else None
        ),
    )
