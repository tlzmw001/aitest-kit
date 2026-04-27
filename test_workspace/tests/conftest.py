"""Shared pytest fixtures for generated integration tests."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from test_workspace.tests.helpers import http as http_helper
from test_workspace.tests.helpers.redis_ops import RedisTracker

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


# ── calibration fixture ──
# Writes test-specific calibration files (999.json) to the service's existing
# calibration directories. The calibrator always picks the highest-numbered file,
# so 999.json overrides the default 1.json during tests.
# AB whitelist is set via AB service API at runtime (PUT /api/v1/ab/whitelist/{user_id}).

_CAL_ON = {"calibration_exp_game": "cal_on", "coarse_rank_exp_game": "cr_off"}
_CAL_OFF = {"calibration_exp_game": "cal_off", "coarse_rank_exp_game": "cr_off"}

_WHITELIST_MAP = {
    "TC-CAL-005": _CAL_OFF,
}
_DEFAULT_WHITELIST = _CAL_ON

_CAL_LINEAR = Path("coupon_system/calibration/scene_game/linear")
_CAL_PIECEWISE = Path("coupon_system/calibration/scene_game/piecewise")
_TEST_FILES = []  # track files created by tests for cleanup

_STD_PW_SEGS = [
    {"range": [0, 0.3], "k": 0.5, "b": 0.1},
    {"range": [0.3, 0.7], "k": 1.0, "b": 0.0},
    {"range": [0.7, 1.0], "k": 1.5, "b": -0.2},
]

_CASE_CONFIGS = {
    "TC-CAL-001": {
        "linear": {"999.json": [{"conditions": {"device": "mobile"}, "k": 1.2, "b": 0.1}]},
    },
    "TC-CAL-002": {
        "linear": {"999.json": [{"conditions": {"device": "mobile"}, "k": 1.2, "b": 0.05}]},
        "piecewise": {"999.json": [{"conditions": {"device": "mobile"}, "segments": _STD_PW_SEGS}]},
    },
    "TC-CAL-003": {
        "linear": {
            "998.json": [{"conditions": {"device": "mobile"}, "k": 0.8, "b": 0}],
            "999.json": [{"conditions": {"device": "mobile"}, "k": 1.3, "b": 0}],
        },
    },
    "TC-CAL-004": {
        "linear": {"999.json": [{"conditions": {"unknown": "x"}, "k": 2.0, "b": 0.0}]},
    },
    "TC-CAL-005": {},
    "TC-CAL-006": {
        "linear": {"999.json": [{"conditions": {"device": "mobile"}, "k": 1.5, "b": 0.1}]},
    },
    "TC-CAL-007": {
        "linear": {"999.json": [
            {"conditions": {"device": "mobile"}, "k": 1.2, "b": 0.0},
            {"conditions": {"device": "mobile"}, "k": 2.0, "b": 0.0},
        ]},
    },
    "TC-CAL-008": {
        "linear": {"999.json": [{"conditions": {"gender": "male"}, "k": 2.0, "b": 0.0}]},
    },
    "TC-CAL-009": {
        "linear": {"999.json": [{"conditions": {"unknown_field": "x"}, "k": 2.0, "b": 0.0}]},
    },
    "TC-CAL-010": {
        "linear": {"999.json": [{"conditions": {"device": "mobile"}, "k": 1.5, "b": 0.0}]},
    },
    "TC-CAL-011": {
        "piecewise": {"999.json": [{"conditions": {"device": "mobile"}, "segments": _STD_PW_SEGS}]},
    },
    "TC-CAL-012": {
        "linear": {"999.json": [{"conditions": {"device": "mobile"}, "k": 1.2, "b": 0.05}]},
        "piecewise": {"999.json": [{"conditions": {"device": "mobile"}, "segments": _STD_PW_SEGS}]},
    },
    "TC-CAL-013": {
        "linear": {"999.json": [{"conditions": {"device": "ios"}, "k": 2.0, "b": 0.0}]},
        "piecewise": {"999.json": [{"conditions": {"device": "ios"}, "segments": _STD_PW_SEGS}]},
    },
    "TC-CAL-014": {
        "linear": {
            "998.json": [{"conditions": {"device": "mobile"}, "k": 1.1, "b": 0}],
            "999.json": [{"conditions": {"device": "mobile"}, "k": 1.8, "b": 0}],
        },
    },
    # ── boundary ──
    # TC-CAL-015/016/019: BLOCKED — need custom calibration_dir, no runtime override API
    "TC-CAL-017": {"linear_raw": {"999.json": "{bad json"}},
    "TC-CAL-018": {"linear_raw": {"999.json": '{"conditions":{"device":"mobile"},"k":2,"b":0}'}},
    "TC-CAL-022": {
        "piecewise": {"999.json": [{"conditions": {"device": "mobile"}, "segments": [
            {"range": [0.7, 0.3], "k": 2.0, "b": 0.0},
            {"range": [0, 1], "k": 1.0, "b": 0.0},
        ]}]},
    },
    "TC-CAL-023": {
        "linear": {"999.json": [{"conditions": {"external": "0"}, "k": 1.5, "b": 0}]},
    },
    "TC-CAL-024": {
        "linear": {"999.json": [{"conditions": {"isPrior": "true"}, "k": 2, "b": 0}]},
    },
    "TC-CAL-025": {},  # same as 015, blocked
    "TC-CAL-026": {"linear_raw": {"999.json": "{bad json"}},
    "TC-CAL-027": {
        "linear": {"999.json": [{"conditions": {"external": "0"}, "k": 1.5, "b": 0}]},
    },
}


def _cleanup_test_files():
    for f in _TEST_FILES:
        try:
            f.unlink(missing_ok=True)
        except OSError:
            pass
    _TEST_FILES.clear()


@pytest.fixture
def setup_calibration(http_base_url, ab_base_url):
    """Per-case calibration setup: write test calibration files + set AB whitelist + init stock."""

    _whitelist_users = []

    def _setup(case_id: str):
        _cleanup_test_files()

        config = _CASE_CONFIGS.get(case_id, {})
        tc_num = case_id.split("-")[-1].lower()
        user_id = f"u_cal_{tc_num}"

        for key, target_dir in [("linear", _CAL_LINEAR), ("piecewise", _CAL_PIECEWISE)]:
            files = config.get(key)
            if files is not None:
                for fname, rules in files.items():
                    path = target_dir / fname
                    path.write_text(json.dumps(rules))
                    _TEST_FILES.append(path)

        raw_files = config.get("linear_raw")
        if raw_files is not None:
            for fname, content in raw_files.items():
                path = _CAL_LINEAR / fname
                path.write_text(content)
                _TEST_FILES.append(path)

        strategy_map = _WHITELIST_MAP.get(case_id, _DEFAULT_WHITELIST)
        http_helper.put(
            ab_base_url,
            f"/api/v1/ab/whitelist/{user_id}",
            json={"strategy_map": strategy_map},
        )
        _whitelist_users.append(user_id)

        coupon_id = "COUPON_CAL_BOUNDARY_001" if int(tc_num) >= 15 else "COUPON_CAL_001"
        http_helper.post(http_base_url, "/api/v1/admin/stock", json={
            "coupon_id": coupon_id, "stock": 100, "ttl": 86400,
        })

    yield _setup

    _cleanup_test_files()
    for uid in _whitelist_users:
        try:
            http_helper.delete(ab_base_url, f"/api/v1/ab/whitelist/{uid}")
        except Exception:
            pass
    _whitelist_users.clear()
