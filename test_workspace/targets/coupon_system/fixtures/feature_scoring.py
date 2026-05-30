"""Feature scoring module fixtures."""
from __future__ import annotations

import pytest

from test_workspace.targets.coupon_system.helpers import http as http_helper


_AB_OFF = {"coarse_rank_exp_game": "cr_off", "calibration_exp_game": "cal_off"}

_STOCK_IDS = [
    "COUPON_FEAT_001",
    "COUPON_FEAT_OK",
    "COUPON_FEAT_MISSING",
    "COUPON_FEAT_BAD",
    "COUPON_FEAT_NOT_IN_TSV",
    "COUPON_FEAT_NO_FILE",
]

_USER_FEATURES = {
    "gender": "male",
    "age": 28,
    "total_spend": 30000,
    "purchase_frequency": 4,
    "register_days": 120,
    "is_new_user": True,
    "is_member": True,
}

_CASE_USERS = {
    "TC-FEAT-001": "u_feat_http",
    "TC-FEAT-002": "u_feat_grpc",
    "TC-FEAT-003": "u_feat_item_merge",
    "TC-SCORE-001": "u_score_internal_http",
    "TC-SCORE-002": "u_score_internal_grpc",
    "TC-SCORE-003": "u_score_external_http",
    "TC-SCORE-004": "u_score_external_grpc",
    "TC-SCORE-005": "u_score_encrypt",
    "TC-FEAT-004": "u_feat_missing",
    "TC-FEAT-006": "u_feat_no_file",
    "TC-FEAT-007": "u_feat_ok",
    "TC-FEAT-008": "u_feat_bad",
    "TC-FEAT-009": "u_feat_not_in_tsv",
}

_CASE_USER_FEATURES = {
    "TC-FEAT-001": {
        **_USER_FEATURES,
        "gender": "male",
        "total_spend": 1200,
    },
    "TC-FEAT-002": {
        **_USER_FEATURES,
        "age": 30,
        "is_member": True,
    },
    "TC-FEAT-004": None,
}


@pytest.fixture
def setup_feature_scoring(http_base_url, ab_base_url):
    """Prepare stock and user features for feature/scoring cases."""
    whitelist_users: list[str] = []

    def _setup(case_id: str):
        tc_num = case_id.split("-")[-1].lower()
        user_id = _CASE_USERS.get(case_id, f"u_feat_{tc_num}")

        http_helper.put(
            ab_base_url,
            f"/api/v1/ab/whitelist/{user_id}",
            json={"strategy_map": _AB_OFF},
        )
        whitelist_users.append(user_id)

        features = _CASE_USER_FEATURES.get(case_id, _USER_FEATURES)
        if features is not None:
            http_helper.post(
                http_base_url,
                "/api/v1/admin/user-features",
                json={"user_id": user_id, "features": features},
            )

        for coupon_id in _STOCK_IDS:
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
