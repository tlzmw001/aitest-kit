"""Shared pytest fixtures for generated integration tests."""
from __future__ import annotations

import os

import pytest

from test_workspace.tests.helpers.redis_ops import RedisTracker

pytest_plugins: list[str] = []


@pytest.fixture(scope="session")
def http_base_url() -> str:
    base_url = os.environ.get("AITEST_HTTP_BASE_URL")
    if not base_url:
        pytest.fail("AITEST_HTTP_BASE_URL is required for generated HTTP tests")
    return base_url


@pytest.fixture(scope="session")
def grpc_target() -> str:
    target = os.environ.get("AITEST_GRPC_TARGET")
    if not target:
        pytest.fail("AITEST_GRPC_TARGET is required for generated gRPC tests")
    return target


@pytest.fixture(scope="session")
def redis_url() -> str:
    value = os.environ.get("AITEST_REDIS_URL")
    if not value:
        pytest.fail("AITEST_REDIS_URL is required for Redis-backed tests")
    return value


@pytest.fixture
def redis_tracker(redis_url: str) -> RedisTracker:
    tracker = RedisTracker(url=redis_url)
    yield tracker
    tracker.close()
