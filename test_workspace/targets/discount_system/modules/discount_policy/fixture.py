"""Pytest fixture for the discount policy harness."""
from __future__ import annotations

import pytest

from aitest_kit.runtime_variables import require_env

from .harness import DiscountPolicyHarness


@pytest.fixture
def setup_discount_policy() -> DiscountPolicyHarness:
    harness = DiscountPolicyHarness(require_env("DISCOUNT_SYSTEM_BASE_URL"))
    try:
        yield harness
    finally:
        harness.cleanup()
        harness.close()
