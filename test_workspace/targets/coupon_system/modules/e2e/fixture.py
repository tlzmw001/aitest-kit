"""Public pytest fixture for the e2e module Harness."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from .harness import E2eHarness


@pytest.fixture
def setup_e2e() -> Iterator[E2eHarness]:
    harness = E2eHarness()
    try:
        yield harness
    finally:
        harness.close()
