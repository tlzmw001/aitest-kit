"""Shared pytest fixtures for generated tests."""
from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session")
def http_base_url() -> str:
    value = os.environ.get("HTTP_BASE_URL")
    if not value:
        pytest.fail("HTTP_BASE_URL is required for generated HTTP tests")
    return value


@pytest.fixture(scope="session")
def grpc_target() -> str:
    value = os.environ.get("GRPC_TARGET")
    if not value:
        pytest.fail("GRPC_TARGET is required for generated gRPC tests")
    return value

