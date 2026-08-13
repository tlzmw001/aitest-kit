"""Pytest entry point for the calibration Harness."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from .harness import CalibrationHarness


@pytest.fixture
def setup_calibration() -> Iterator[CalibrationHarness]:
    harness = CalibrationHarness()
    try:
        yield harness
    finally:
        harness.close()
