"""Single public pytest fixture for the rough_ranking module."""
from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

import pytest

from aitest_kit.runtime_variables import require_envs
from test_workspace.targets.coupon_system.helpers.redis_ops import RedisTracker
from test_workspace.targets.coupon_system.modules.rough_ranking.harness import RoughRankingHarness


@pytest.fixture
def setup_rough_ranking() -> Iterator[RoughRankingHarness]:
    env = require_envs(("AB_SERVICE_URL", "REDIS_URL"))
    with ExitStack() as stack:
        workspace = Path(stack.enter_context(TemporaryDirectory(prefix="aitest_rank_")))
        redis_tracker = RedisTracker(url=env["REDIS_URL"])
        stack.callback(redis_tracker.close)
        harness = RoughRankingHarness(
            ab_base_url=env["AB_SERVICE_URL"],
            redis_tracker=redis_tracker,
            workspace=workspace,
        )
        stack.callback(harness.close)
        yield harness
