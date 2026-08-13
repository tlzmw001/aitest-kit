from __future__ import annotations

from collections.abc import Iterator

import pytest

from aitest_kit.runtime_variables import PreconditionMissing
from test_workspace.targets.coupon_system.modules.ab_experiment.fixture import setup_ab_experiment
from test_workspace.targets.coupon_system.modules.calibration.fixture import setup_calibration
from test_workspace.targets.coupon_system.modules.e2e.fixture import setup_e2e
from test_workspace.targets.coupon_system.modules.feature_scoring.fixture import setup_feature_scoring
from test_workspace.targets.coupon_system.modules.issuance.fixture import setup_issuance
from test_workspace.targets.coupon_system.modules.scene_routing.fixture import setup_scene_routing
from test_workspace.targets.coupon_system.modules.validation_ratelimit.fixture import setup_validation_ratelimit


_FIXTURES = (
    setup_ab_experiment,
    setup_calibration,
    setup_e2e,
    setup_feature_scoring,
    setup_issuance,
    setup_scene_routing,
    setup_validation_ratelimit,
)


@pytest.mark.parametrize("fixture", _FIXTURES)
def test_public_module_fixture_does_not_require_unused_environment(fixture, monkeypatch, tmp_path):
    monkeypatch.setenv("AITEST_ENV_FILE", str(tmp_path / "missing.env"))
    for name in (
        "COUPON_SYSTEM_BASE_URL",
        "COUPON_AB_BASE_URL",
        "COUPON_GRPC_TARGET",
        "HTTP_BASE_URL",
        "AB_SERVICE_URL",
        "GRPC_TARGET",
        "REDIS_URL",
        "COUPON_CONFIG_PATH",
    ):
        monkeypatch.delenv(name, raising=False)

    value = fixture.__wrapped__()
    if isinstance(value, Iterator):
        harness = next(value)
        value.close()
    else:
        harness = value
        harness.close()

    assert harness is not None


def test_grpc_capability_requires_only_its_own_environment(monkeypatch, tmp_path):
    from test_workspace.targets.coupon_system.modules.ab_experiment import harness as module

    monkeypatch.setenv("AITEST_ENV_FILE", str(tmp_path / "missing.env"))
    monkeypatch.setenv("COUPON_GRPC_TARGET", "127.0.0.1:50051")
    monkeypatch.delenv("COUPON_SYSTEM_BASE_URL", raising=False)
    monkeypatch.delenv("COUPON_AB_BASE_URL", raising=False)
    monkeypatch.setattr(module.grpc_ops, "recommend", lambda target, body: {"target": target, "body": body})

    harness = module.AbExperimentHarness()
    try:
        result = harness.recommend_grpc()
    finally:
        harness.close()

    assert result["target"] == "127.0.0.1:50051"


def test_missing_environment_is_reported_when_capability_is_used(monkeypatch, tmp_path):
    from test_workspace.targets.coupon_system.modules.ab_experiment.harness import AbExperimentHarness

    monkeypatch.setenv("AITEST_ENV_FILE", str(tmp_path / "missing.env"))
    monkeypatch.delenv("COUPON_SYSTEM_BASE_URL", raising=False)
    harness = AbExperimentHarness()
    try:
        with pytest.raises(PreconditionMissing, match="COUPON_SYSTEM_BASE_URL"):
            harness.prepare_stock()
    finally:
        harness.close()
