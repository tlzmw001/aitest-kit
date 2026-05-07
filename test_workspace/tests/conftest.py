"""Shared pytest fixtures for generated integration tests."""
from __future__ import annotations

import os

import pytest

from test_workspace.tests.helpers.redis_ops import RedisTracker

pytest_plugins = [
    "test_workspace.tests.fixtures.ab_experiment",
    "test_workspace.tests.fixtures.ab_service",
    "test_workspace.tests.fixtures.calibration",
    "test_workspace.tests.fixtures.e2e",
    "test_workspace.tests.fixtures.feature_scoring",
    "test_workspace.tests.fixtures.issuance",
    "test_workspace.tests.fixtures.logging",
    "test_workspace.tests.fixtures.rough_ranking",
    "test_workspace.tests.fixtures.scene_routing",
    "test_workspace.tests.fixtures.validation_ratelimit",
    "test_workspace.tests.fixtures.discount_policy",
]

# ── session fixtures ──


@pytest.fixture(scope="session")
def http_base_url():
    return os.environ.get("HTTP_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def grpc_target():
    return os.environ.get("GRPC_TARGET", "localhost:50051")


@pytest.fixture(scope="session")
def ab_base_url():
    return os.environ.get("AB_SERVICE_URL", "http://localhost:8100")


@pytest.fixture(scope="session")
def redis_url():
    return os.environ.get("REDIS_URL", "redis://localhost:6379/0")


@pytest.fixture
def redis_tracker(redis_url):
    tracker = RedisTracker(url=redis_url)
    yield tracker
    tracker.close()
