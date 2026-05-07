"""Project-specific gRPC helpers for generated integration tests."""
from __future__ import annotations


def recommend(*_args, **_kwargs) -> dict:
    raise NotImplementedError(
        "Configure test_workspace/tests/helpers/grpc_ops.py for this project's protobuf API"
    )
