"""Public pytest fixture for the validation_ratelimit module Harness."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from .harness import ValidationRatelimitHarness


@pytest.fixture
def setup_validation_ratelimit() -> Iterator[ValidationRatelimitHarness]:
    harness = ValidationRatelimitHarness()
    try:
        yield harness
    finally:
        harness.close()
