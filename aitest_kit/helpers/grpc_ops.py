"""Placeholder gRPC helpers for generated pytest.

Real gRPC projects should provide target-local helpers under
``test_workspace/targets/{target}/helpers/grpc_ops.py``.
"""
from __future__ import annotations

from typing import Any


def call(*args: Any, **kwargs: Any) -> dict[str, Any]:
    raise RuntimeError(
        "No target-local gRPC helper is configured. Create "
        "test_workspace/targets/{target}/helpers/grpc_ops.py for this suite."
    )


def recommend(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return call(*args, **kwargs)
