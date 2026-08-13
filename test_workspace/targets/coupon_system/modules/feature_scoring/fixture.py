"""Pytest entry point for the feature_scoring Harness."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from .harness import FeatureScoringHarness


@pytest.fixture
def setup_feature_scoring() -> Iterator[FeatureScoringHarness]:
    harness = FeatureScoringHarness()
    try:
        yield harness
    finally:
        harness.close()
