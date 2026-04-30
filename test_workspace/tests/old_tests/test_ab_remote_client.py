from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from ab_experiment_sdk import ABExperimentRequest
from ab_experiment_sdk.remote_client import RemoteABExperimentSDK
from ab_experiment_sdk.service import create_app


def _build_service_client(tmp_path: Path) -> TestClient:
    experiments_path = tmp_path / "experiments.json"
    payload = {
        "experiments": [
            {
                "name": "exp_game",
                "strategies": [
                    {"id": "game_on", "hash_range": [0, 100], "params": {"k": 1}}
                ],
            },
            {
                "name": "exp_cal",
                "strategies": [
                    {"id": "cal_on", "hash_range": [0, 100], "params": {"b": 2}}
                ],
            },
        ]
    }
    experiments_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    app = create_app(
        experiments_path=str(experiments_path),
        initial_whitelist={"u1": {"exp_game": "game_on"}},
    )
    return TestClient(app)


def test_remote_evaluate_round_trip(tmp_path):
    service_client = _build_service_client(tmp_path)
    sdk = RemoteABExperimentSDK(base_url="http://testserver", client=service_client)

    response = sdk.evaluate(ABExperimentRequest(
        user_id="u1",
        request_id="rid-1",
        experiment_names=["exp_game"],
    ))
    assert response.request_id == "rid-1"
    assert "exp_game" in response.assignments
    assert response.assignments["exp_game"].strategy_id == "game_on"
    assert response.assignments["exp_game"].hit_reason == "whitelist"

    sdk.close()


def test_remote_whitelist_methods(tmp_path):
    service_client = _build_service_client(tmp_path)
    sdk = RemoteABExperimentSDK(base_url="http://testserver", client=service_client)

    sdk.set_user_whitelist("u2", {"exp_cal": "cal_on"})
    response = sdk.evaluate(ABExperimentRequest(
        user_id="u2",
        experiment_names=["exp_cal"],
    ))
    assert response.assignments["exp_cal"].strategy_id == "cal_on"
    assert response.assignments["exp_cal"].hit_reason == "whitelist"

    sdk.clear_whitelist("u2")
    response = service_client.get("/api/v1/ab/whitelist")
    assert "u2" not in response.json()

    sdk.set_whitelist({"u3": {"exp_game": "game_on"}})
    assert sdk.get_whitelist() == {"u3": {"exp_game": "game_on"}}

    sdk.clear_whitelist()
    assert sdk.get_whitelist() == {}
    sdk.close()


def test_remote_client_raises_on_http_error():
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "internal error"})

    mock_client = httpx.Client(
        transport=httpx.MockTransport(_handler),
        base_url="http://ab.test",
    )
    sdk = RemoteABExperimentSDK(base_url="http://ab.test", client=mock_client)

    with pytest.raises(httpx.HTTPStatusError):
        sdk.evaluate(ABExperimentRequest(user_id="u_err"))

    sdk.close()
