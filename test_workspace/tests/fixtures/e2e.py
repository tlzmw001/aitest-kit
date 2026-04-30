"""E2E module fixtures."""
from __future__ import annotations

import pytest

from test_workspace.tests.helpers import http as http_helper


_E2E_WHITELIST = {
    "coarse_rank_exp_game": "cr_v2_full",
    "calibration_exp_game": "cal_on",
}


@pytest.fixture
def setup_e2e(http_base_url, ab_base_url):
    """Prepare stock and optional AB whitelist for end-to-end cases."""
    whitelist_users: list[str] = []

    def _setup(case_id: str):
        tc_num = case_id.split("-")[-1].lower()
        user_id = f"u_e2e_{tc_num}"
        if case_id in {"TC-E2E-001", "TC-E2E-004"}:
            http_helper.put(
                ab_base_url,
                f"/api/v1/ab/whitelist/{user_id}",
                json={"strategy_map": _E2E_WHITELIST},
            )
            whitelist_users.append(user_id)

        for coupon_id in ("COUPON_ACT_001", "COUPON_SHIP_001"):
            http_helper.post(
                http_base_url,
                "/api/v1/admin/stock",
                json={"coupon_id": coupon_id, "stock": 100, "ttl": 86400},
            )

    yield _setup

    for user_id in whitelist_users:
        try:
            http_helper.delete(ab_base_url, f"/api/v1/ab/whitelist/{user_id}")
        except Exception:
            pass
