"""Shared module_type resolution and requirement checks for codegen."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aitest_kit.codegen.project_config import ProjectConfig


@dataclass(frozen=True)
class ModuleTypeResolution:
    module_type: str | None
    source: str


@dataclass(frozen=True)
class ModuleTypeDiagnostic:
    code: str
    message: str
    source: str = "module_type"


def resolve_module_type(
    module: str,
    profile_data: dict[str, Any],
    project: ProjectConfig,
) -> ModuleTypeResolution:
    """Resolve module_type from the currently supported fact sources.

    New registry-backed module.yaml defaults will be wired through this function
    later. For now this preserves legacy behavior: profile wins, then
    project_config.modules, then missing.
    """
    profile_module_type = profile_data.get("module_type")
    if isinstance(profile_module_type, str) and profile_module_type.strip():
        return ModuleTypeResolution(profile_module_type.strip(), "profile.module_type")

    module_config = project.modules.get(module, {})
    config_module_type = (
        module_config.get("module_type")
        if isinstance(module_config, dict)
        else None
    )
    if isinstance(config_module_type, str) and config_module_type.strip():
        return ModuleTypeResolution(
            config_module_type.strip(),
            f"project_config.modules.{module}.module_type",
        )

    return ModuleTypeResolution(None, "missing")


def validate_module_type_requirements(
    resolution: ModuleTypeResolution,
    project: ProjectConfig,
    profile_data: dict[str, Any],
    case_bodies: dict[str, Any],
    case_flows: dict[str, Any],
) -> list[ModuleTypeDiagnostic]:
    """Validate module_type exists in config and required profile sections exist."""
    module_type = resolution.module_type
    if not module_type:
        return []

    module_type_cfg = project.module_types.get(module_type)
    if module_type_cfg is None:
        return [
            ModuleTypeDiagnostic(
                "E504",
                f"unknown module_type={module_type}",
            )
        ]

    diagnostics: list[ModuleTypeDiagnostic] = []
    for required in module_type_cfg.get("requires", []):
        if required == "case_bodies":
            if not (case_bodies or case_flows):
                diagnostics.append(
                    ModuleTypeDiagnostic(
                        "E504",
                        f"module_type={module_type} requires case_bodies or case_flows",
                    )
                )
            continue
        if not profile_data.get(required):
            diagnostics.append(
                ModuleTypeDiagnostic(
                    "E504",
                    f"module_type={module_type} requires {required}",
                )
            )
    return diagnostics
