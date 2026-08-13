"""Single public pytest fixture for the ab_service module."""
from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

import pytest

from aitest_kit.runtime_variables import require_env
from test_workspace.targets.coupon_system.modules.ab_service.api import ABApiClient
from test_workspace.targets.coupon_system.modules.ab_service.harness import AbServiceHarness


@pytest.fixture
def setup_ab_service() -> Iterator[AbServiceHarness]:
    base_url = require_env("COUPON_AB_BASE_URL")
    with ExitStack() as stack:
        workspace = Path(stack.enter_context(TemporaryDirectory(prefix="aitest_abs_")))
        harness = AbServiceHarness(api=ABApiClient(base_url), workspace=workspace)
        stack.callback(harness.close)
        yield harness
