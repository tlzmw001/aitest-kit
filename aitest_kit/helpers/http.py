"""Generic HTTP helpers for generated pytest."""
from __future__ import annotations

from typing import Any

import httpx


_client = httpx.Client(transport=httpx.HTTPTransport())


def post(base_url: str, path: str, json: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
    response = post_response(base_url, path, json=json, timeout=timeout)
    response.raise_for_status()
    return response.json()


def post_response(
    base_url: str,
    path: str,
    json: dict[str, Any],
    timeout: float = 10.0,
) -> httpx.Response:
    url = f"{base_url.rstrip('/')}{path}"
    return _client.post(url, json=json, timeout=timeout)


def get(base_url: str, path: str, timeout: float = 10.0) -> dict[str, Any]:
    response = get_response(base_url, path, timeout=timeout)
    response.raise_for_status()
    return response.json()


def get_response(base_url: str, path: str, timeout: float = 10.0) -> httpx.Response:
    url = f"{base_url.rstrip('/')}{path}"
    return _client.get(url, timeout=timeout)


def put(base_url: str, path: str, json: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    response = _client.put(url, json=json, timeout=timeout)
    response.raise_for_status()
    return response.json()


def delete(base_url: str, path: str, timeout: float = 10.0) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    response = _client.delete(url, timeout=timeout)
    response.raise_for_status()
    return response.json()

