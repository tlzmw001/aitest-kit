"""Public HTTP API adapter with reversible AB service state changes."""
from __future__ import annotations

import logging
from typing import Any

import httpx


logger = logging.getLogger(__name__)


class ABApiClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            transport=httpx.HTTPTransport(),
            timeout=10.0,
        )
        self._experiment_snapshots: dict[str, dict[str, Any] | None] = {}
        self._whitelist_snapshot: dict[str, Any] | None = None

    def request(self, method: str, path: str, json_body: dict[str, Any] | None = None) -> httpx.Response:
        return self._client.request(method, path, json=json_body)

    def get(self, path: str) -> httpx.Response:
        return self.request("GET", path)

    def post(self, path: str, json_body: dict[str, Any] | None = None) -> httpx.Response:
        return self.request("POST", path, json_body)

    def put(self, path: str, json_body: dict[str, Any] | None = None) -> httpx.Response:
        return self.request("PUT", path, json_body)

    def delete(self, path: str) -> httpx.Response:
        return self.request("DELETE", path)

    def snapshot_whitelist(self) -> None:
        if self._whitelist_snapshot is not None:
            return
        response = self.get("/api/v1/ab/whitelist")
        response.raise_for_status()
        body = response.json()
        self._whitelist_snapshot = body if isinstance(body, dict) else {}

    def snapshot_experiment(self, name: str) -> None:
        if name in self._experiment_snapshots:
            return
        response = self.get(f"/api/v1/ab/experiments/{name}")
        if response.status_code == 200:
            self._experiment_snapshots[name] = response.json()
        elif response.status_code == 404:
            self._experiment_snapshots[name] = None
        else:
            response.raise_for_status()

    def upsert_experiment(self, payload: dict[str, Any]) -> None:
        name = payload["name"]
        self.snapshot_experiment(name)
        response = self.post("/api/v1/ab/experiments", payload)
        if response.status_code == 409:
            response = self.put(f"/api/v1/ab/experiments/{name}", payload)
        response.raise_for_status()

    def set_user_whitelist(self, user_id: str, strategy_map: dict[str, str]) -> None:
        self.snapshot_whitelist()
        response = self.put(
            f"/api/v1/ab/whitelist/{user_id}",
            {"strategy_map": strategy_map},
        )
        response.raise_for_status()

    def replace_whitelist(self, whitelist: dict[str, dict[str, str]]) -> None:
        self.snapshot_whitelist()
        response = self.put("/api/v1/ab/whitelist", whitelist)
        response.raise_for_status()

    def close(self) -> None:
        try:
            self._restore()
        finally:
            self._client.close()

    def _restore(self) -> None:
        if self._whitelist_snapshot is not None:
            response = self.put("/api/v1/ab/whitelist", self._whitelist_snapshot)
            if response.status_code >= 400:
                logger.warning("restore AB whitelist failed: %s %s", response.status_code, response.text)
        for name, payload in reversed(list(self._experiment_snapshots.items())):
            if payload is None:
                response = self.delete(f"/api/v1/ab/experiments/{name}")
                if response.status_code not in {200, 404}:
                    logger.warning("delete AB experiment failed: %s %s", name, response.text)
                continue
            response = self.put(f"/api/v1/ab/experiments/{name}", payload)
            if response.status_code == 404:
                response = self.post("/api/v1/ab/experiments", payload)
            if response.status_code >= 400:
                logger.warning("restore AB experiment failed: %s %s", name, response.text)
