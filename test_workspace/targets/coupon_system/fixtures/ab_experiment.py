"""AB experiment module fixtures."""
from __future__ import annotations

import pytest

from test_workspace.targets.coupon_system.helpers import http as http_helper


_BASE_STOCK = {
    "COUPON_AB_001": 100,
    "COUPON_AB_BOUNDARY_001": 100,
}

_WHITELIST_MAP = {
    "TC-AB-003": {
        "coarse_rank_exp_game": "cr_off",
        "calibration_exp_game": "cal_off",
    },
    "TC-AB-012": {
        "coarse_rank_exp_game": "not_exists_strategy",
    },
}

_USER_BY_CASE = {
    "TC-AB-003": "u_ab_white",
    "TC-AB-012": "u_ab_invalid_white",
}


@pytest.fixture
def setup_ab_experiment(http_base_url, ab_base_url):
    """Prepare stock and optional AB whitelist for ab_experiment cases."""
    whitelist_users: list[str] = []

    def _setup(case_id: str):
        for coupon_id, stock in _BASE_STOCK.items():
            http_helper.post(
                http_base_url,
                "/api/v1/admin/stock",
                json={"coupon_id": coupon_id, "stock": stock, "ttl": 86400},
            )

        strategy_map = _WHITELIST_MAP.get(case_id)
        if strategy_map:
            user_id = _USER_BY_CASE.get(case_id, f"u_ab_{case_id.split('-')[-1].lower()}")
            http_helper.put(
                ab_base_url,
                f"/api/v1/ab/whitelist/{user_id}",
                json={"strategy_map": strategy_map},
            )
            whitelist_users.append(user_id)

    yield _setup

    for user_id in whitelist_users:
        try:
            http_helper.delete(ab_base_url, f"/api/v1/ab/whitelist/{user_id}")
        except Exception:
            pass
