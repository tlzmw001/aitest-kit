"""Scene routing module fixtures."""
from __future__ import annotations

import pytest

from test_workspace.targets.coupon_system.helpers import http as http_helper


_FALLBACK_CASES = {
    "TC-ROUTE-007": {"coupon:fallback:score:3001": "0.8", "coupon:fallback:score:default": "0.6"},
    "TC-ROUTE-008": {"coupon:fallback:score:default": "0.6"},
    "TC-ROUTE-009": {},
    "TC-ROUTE-010": {"coupon:fallback:score:3001": "not-a-number", "coupon:fallback:score:default": "0.6"},
    "TC-ROUTE-011": {"coupon:fallback:score:default": "not-a-number"},
    "TC-ROUTE-017": {"coupon:fallback:score:3001": "not-a-number", "coupon:fallback:score:default": "0.6"},
}


@pytest.fixture
def setup_scene_routing(http_base_url, redis_tracker):
    """Prepare stock for scene routing cases."""

    def _setup(case_id: str):
        for coupon_id in ("COUPON_ROUTE_001", "COUPON_ROUTE_BOUNDARY_001"):
            http_helper.post(
                http_base_url,
                "/api/v1/admin/stock",
                json={"coupon_id": coupon_id, "stock": 100, "ttl": 86400},
            )

        if case_id in _FALLBACK_CASES:
            redis_tracker.delete("coupon:fallback:score:3001", "coupon:fallback:score:default")
            for key, value in _FALLBACK_CASES[case_id].items():
                redis_tracker.set(key, value, ex=86400)

    yield _setup
