"""Pytest fixture for the coupon logging harness."""
from __future__ import annotations

import pytest

from aitest_kit.runtime_variables import require_envs

from .harness import LoggingHarness


@pytest.fixture
def setup_logging() -> LoggingHarness:
    env = require_envs(["COUPON_AB_BASE_URL", "REDIS_URL"])
    harness = LoggingHarness(
        ab_base_url=env["COUPON_AB_BASE_URL"],
        redis_url=env["REDIS_URL"],
    )
    try:
        yield harness
    finally:
        harness.close()
