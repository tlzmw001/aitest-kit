"""Calibration module fixtures: per-case calibration file setup + AB whitelist."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from test_workspace.tests.helpers import http as http_helper


_CAL_ON = {"calibration_exp_game": "cal_on", "coarse_rank_exp_game": "cr_off"}
_CAL_OFF = {"calibration_exp_game": "cal_off", "coarse_rank_exp_game": "cr_off"}

_WHITELIST_MAP = {
    "TC-CAL-005": _CAL_OFF,
}
_DEFAULT_WHITELIST = _CAL_ON

_CAL_EXPERIMENT_NAME = "calibration_exp_game"
_CAL_ON_STRATEGY_ID = "cal_on"

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
    "TC-CAL-015": {"missing_dirs": True},
    "TC-CAL-016": {"empty_dirs": True},
    "TC-CAL-017": {"linear_raw": {"999.json": "{bad json"}},
    "TC-CAL-018": {"linear_raw": {"999.json": '{"conditions":{"device":"mobile"},"k":2,"b":0}'}},
    "TC-CAL-019": {"empty_path": True},
    "TC-CAL-022": {
        "piecewise": {"999.json": [{"conditions": {"device": "mobile"}, "segments": [
            {"range": [0.7, 0.3], "k": 2.0, "b": 0.0},
            {"range": [0, 1], "k": 1.0, "b": 0.0},
        ]}]},
    },
    "TC-CAL-023": {
        "linear": {"999.json": [{"conditions": {"external": "0"}, "k": 1.5, "b": 0}]},
    },
    "TC-CAL-025": {"missing_dirs": True},
    "TC-CAL-026": {"linear_raw": {"999.json": "{bad json"}},
    "TC-CAL-027": {
        "linear": {"999.json": [{"conditions": {"external": "0"}, "k": 1.5, "b": 0}]},
    },
}


def _write_json_rules(target_dir: Path, files: dict) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for fname, rules in files.items():
        (target_dir / fname).write_text(json.dumps(rules))


def _write_raw_rules(target_dir: Path, files: dict) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for fname, content in files.items():
        (target_dir / fname).write_text(content)


def _replace_calibration_dir(experiment: dict, calibration_dir: dict) -> dict:
    patched = json.loads(json.dumps(experiment))
    for strategy in patched.get("strategies", []):
        if strategy.get("id") != _CAL_ON_STRATEGY_ID:
            continue
        params = strategy.setdefault("params", {})
        params["enable_calibration"] = True
        params["calibration_dir"] = dict(calibration_dir)
        break
    return patched


@pytest.fixture
def setup_calibration(http_base_url, ab_base_url, tmp_path):
    """Per-case calibration setup: isolate calibration dirs + set AB whitelist + init stock."""

    _whitelist_users = []
    _original_experiment = None

    def _setup(case_id: str):
        nonlocal _original_experiment

        config = _CASE_CONFIGS.get(case_id, {})
        tc_num = case_id.split("-")[-1].lower()
        user_id = f"u_cal_{tc_num}"

        original_experiment = http_helper.get(
            ab_base_url,
            f"/api/v1/ab/experiments/{_CAL_EXPERIMENT_NAME}",
        )
        _original_experiment = original_experiment

        case_dir = tmp_path / case_id.lower()
        linear_dir = case_dir / "linear"
        piecewise_dir = case_dir / "piecewise"

        if config.get("missing_dirs"):
            calibration_dir = {
                "linear": str(case_dir / "missing_linear"),
                "piecewise": str(case_dir / "missing_piecewise"),
            }
        elif config.get("empty_dirs"):
            linear_dir.mkdir(parents=True, exist_ok=True)
            piecewise_dir.mkdir(parents=True, exist_ok=True)
            calibration_dir = {
                "linear": str(linear_dir),
                "piecewise": str(piecewise_dir),
            }
        elif config.get("empty_path"):
            calibration_dir = {"linear": "", "piecewise": ""}
        else:
            linear_files = config.get("linear")
            piecewise_files = config.get("piecewise")
            raw_linear_files = config.get("linear_raw")

            if linear_files is not None:
                _write_json_rules(linear_dir, linear_files)
            elif raw_linear_files is not None:
                _write_raw_rules(linear_dir, raw_linear_files)
            else:
                linear_dir.mkdir(parents=True, exist_ok=True)

            if piecewise_files is not None:
                _write_json_rules(piecewise_dir, piecewise_files)
            else:
                piecewise_dir.mkdir(parents=True, exist_ok=True)

            calibration_dir = {
                "linear": str(linear_dir),
                "piecewise": str(piecewise_dir),
            }

        if _WHITELIST_MAP.get(case_id, _DEFAULT_WHITELIST).get(_CAL_EXPERIMENT_NAME) == _CAL_ON_STRATEGY_ID:
            http_helper.put(
                ab_base_url,
                f"/api/v1/ab/experiments/{_CAL_EXPERIMENT_NAME}",
                json=_replace_calibration_dir(original_experiment, calibration_dir),
            )

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

    if _original_experiment is not None:
        try:
            http_helper.put(
                ab_base_url,
                f"/api/v1/ab/experiments/{_CAL_EXPERIMENT_NAME}",
                json=_original_experiment,
            )
        except Exception:
            pass
    for uid in _whitelist_users:
        try:
            http_helper.delete(ab_base_url, f"/api/v1/ab/whitelist/{uid}")
        except Exception:
            pass
    _whitelist_users.clear()
