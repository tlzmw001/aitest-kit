"""Configuration registry for target/module/suite/task contexts."""
from __future__ import annotations

from aitest_kit.registry.loader import (
    load_module_context,
    load_suite_context,
    load_target_context,
)
from aitest_kit.registry.task_loader import load_task_context
from aitest_kit.registry.models import (
    ModuleContext,
    RegisteredSuite,
    SuiteManifestContext,
    TargetContext,
    TargetDefaults,
    TaskContext,
    TaskUnit,
)

__all__ = [
    "ModuleContext",
    "RegisteredSuite",
    "SuiteManifestContext",
    "TargetContext",
    "TargetDefaults",
    "TaskContext",
    "TaskUnit",
    "load_module_context",
    "load_suite_context",
    "load_target_context",
    "load_task_context",
]
