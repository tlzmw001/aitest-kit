"""Common coupon_system pytest fixtures shared by target modules."""
from __future__ import annotations

import os

import pytest

from test_workspace.targets.coupon_system.helpers.redis_ops import RedisTracker


@pytest.fixture(scope="session")
def http_base_url() -> str:
    return os.environ.get("HTTP_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def grpc_target() -> str:
    return os.environ.get("GRPC_TARGET", "localhost:50051")


@pytest.fixture(scope="session")
def ab_base_url() -> str:
    return os.environ.get("AB_SERVICE_URL", "http://localhost:8100")


@pytest.fixture(scope="session")
def redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://localhost:6379/0")


@pytest.fixture
def redis_tracker(redis_url: str) -> RedisTracker:
    tracker = RedisTracker(url=redis_url)
    try:
        yield tracker
    finally:
        tracker.cleanup()
