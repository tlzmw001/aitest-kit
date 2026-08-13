"""Pytest entry point for the ab_experiment Harness."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from .harness import AbExperimentHarness


@pytest.fixture
def setup_ab_experiment() -> Iterator[AbExperimentHarness]:
    harness = AbExperimentHarness()
    try:
        yield harness
    finally:
        harness.close()
