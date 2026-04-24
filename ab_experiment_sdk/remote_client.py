"""AB 实验远程客户端：通过 HTTP 调用 AB 实验服务。"""
from __future__ import annotations

from typing import Optional

import httpx

from ab_experiment_sdk.client import (
    ABExperimentAssignment,
    ABExperimentRequest,
    ABExperimentResponse,
)


class RemoteABExperimentSDK:
    """实现 ABExperimentSDK Protocol，通过 HTTP 调用 AB 实验服务。"""

    def __init__(
        self,
        base_url: str,
        timeout: float = 2.0,
        client: Optional[httpx.Client] = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
        )

    def evaluate(self, request: ABExperimentRequest) -> ABExperimentResponse:
        payload = {
            "user_id": request.user_id,
            "request_id": request.request_id,
            "context": dict(request.context),
            "experiment_names": request.experiment_names,
        }
        response = self._client.post("/api/v1/ab/evaluate", json=payload)
        response.raise_for_status()
        body = response.json()

        assignments = {}
        for exp_name, val in body.get("assignments", {}).items():
            if not isinstance(val, dict):
                continue
            assignments[exp_name] = ABExperimentAssignment(
                experiment_name=str(val.get("experiment_name", exp_name)),
                strategy_id=str(val.get("strategy_id", "")),
                params=dict(val.get("params", {})),
                hit_reason=str(val.get("hit_reason", "hash")),
            )

        return ABExperimentResponse(
            request_id=str(body.get("request_id", request.request_id)),
            user_id=str(body.get("user_id", request.user_id)),
            assignments=assignments,
            trace_id=str(body.get("trace_id", "")),
        )

    def set_whitelist(self, whitelist: dict) -> None:
        response = self._client.put("/api/v1/ab/whitelist", json=whitelist)
        response.raise_for_status()

    def set_user_whitelist(self, user_id: str, strategy_map: dict) -> None:
        response = self._client.put(
            f"/api/v1/ab/whitelist/{user_id}",
            json={"strategy_map": strategy_map},
        )
        response.raise_for_status()

    def clear_whitelist(self, user_id: Optional[str] = None) -> None:
        if user_id is None:
            response = self._client.delete("/api/v1/ab/whitelist")
        else:
            response = self._client.delete(f"/api/v1/ab/whitelist/{user_id}")
        response.raise_for_status()

    def get_whitelist(self) -> dict:
        response = self._client.get("/api/v1/ab/whitelist")
        response.raise_for_status()
        body = response.json()
        return body if isinstance(body, dict) else {}

    def close(self) -> None:
        self._client.close()
