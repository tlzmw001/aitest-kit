"""Pytest entry point for the scene_routing Harness."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from .harness import SceneRoutingHarness


@pytest.fixture
def setup_scene_routing() -> Iterator[SceneRoutingHarness]:
    harness = SceneRoutingHarness()
    try:
        yield harness
    finally:
        harness.close()
