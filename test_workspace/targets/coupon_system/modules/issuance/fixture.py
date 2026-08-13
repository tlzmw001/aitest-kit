"""Pytest fixture for the coupon issuance harness."""
from __future__ import annotations

import pytest

from .harness import IssuanceHarness


@pytest.fixture
def setup_issuance() -> IssuanceHarness:
    harness = IssuanceHarness()
    try:
        yield harness
    finally:
        harness.close()
