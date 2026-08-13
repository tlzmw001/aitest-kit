from __future__ import annotations

import pytest

from test_workspace.targets.coupon_system.modules.rough_ranking import harness as module


def test_close_restores_experiment_even_when_whitelist_cleanup_fails(monkeypatch, tmp_path):
    class RedisStub:
        def delete(self, *keys):
            return None

    restored: list[tuple[str, str, dict]] = []
    harness = module.RoughRankingHarness(
        ab_base_url="http://ab",
        redis_tracker=RedisStub(),
        workspace=tmp_path,
    )
    harness._whitelist_users.append("u_cleanup")
    harness._original_experiment = {"name": "coarse_rank_exp_game"}
    monkeypatch.setattr(module.http_helper, "delete", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("delete failed")))
    monkeypatch.setattr(module.http_helper, "put", lambda base, path, json: restored.append((base, path, json)))

    with pytest.raises(RuntimeError, match="delete failed"):
        harness.close()

    assert restored == [
        (
            "http://ab",
            "/api/v1/ab/experiments/coarse_rank_exp_game",
            {"name": "coarse_rank_exp_game"},
        )
    ]
