"""Discount policy module fixtures."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx
import pytest

logger = logging.getLogger(__name__)

_client = httpx.Client(transport=httpx.HTTPTransport())


class DiscountPolicyCase:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._request_ids: set[str] = set()

    def request(self, method: str, path: str, json_body: dict[str, Any] | None = None) -> httpx.Response:
        return _client.request(method, f"{self.base_url}{path}", json=json_body, timeout=10.0)

    def health(self) -> httpx.Response:
        return self.request("GET", "/health")

    def evaluate(self, payload: dict[str, Any]) -> httpx.Response:
        request_id = payload.get("request_id")
        if isinstance(request_id, str) and request_id:
            self._request_ids.add(request_id)
        return self.request("POST", "/api/v1/discount/policy", payload)

    def query(self, request_id: str) -> httpx.Response:
        return self.request("GET", f"/api/v1/discount/decisions/{request_id}")

    def delete(self, request_id: str) -> httpx.Response:
        return self.request("DELETE", f"/api/v1/discount/decisions/{request_id}")

    def payload(self, **overrides: Any) -> dict[str, Any]:
        body: dict[str, Any] = {
            "user_id": "u_dp_default",
            "user_level": "normal",
            "item_id": "item_dp_default",
            "item_price": 120.5,
            "scene": "checkout",
            "stock": 5,
            "request_id": "req_dp_default",
        }
        body.update(overrides)
        return body

    def payload_without(self, *fields: str, **overrides: Any) -> dict[str, Any]:
        body = self.payload(**overrides)
        for field in fields:
            body.pop(field, None)
        return body

    def cleanup(self) -> None:
        for request_id in sorted(self._request_ids):
            try:
                response = self.delete(request_id)
            except httpx.HTTPError as exc:
                logger.warning("cleanup discount decision failed: %s %s", request_id, exc)
                continue
            if response.status_code >= 500:
                logger.warning(
                    "cleanup discount decision returned %s: %s",
                    response.status_code,
                    response.text,
                )


@pytest.fixture
def setup_discount_policy():
    """Create a discount_system public API client and clean decisions after each case."""
    base_url = os.environ.get("DISCOUNT_SYSTEM_BASE_URL")
    if not base_url:
        pytest.fail("DISCOUNT_SYSTEM_BASE_URL is required for discount_policy tests")
    case = DiscountPolicyCase(base_url)

    def _setup(case_id: str) -> DiscountPolicyCase:
        return case

    yield _setup
    case.cleanup()
