from pathlib import Path

import pytest

from aitest_kit.registry.loader import load_module_context, load_target_context
from aitest_kit.runtime_variables import require_env

from .harness import LogDemoHarness


@pytest.fixture
def setup_log_demo() -> LogDemoHarness:
    target = load_target_context("demo", workspace_root=Path(__file__).resolve().parents[5])
    module = load_module_context(target, "log_demo")
    return LogDemoHarness(require_env("AITEST_LOG_DEMO_URL"), module.log_capture.source_id)
