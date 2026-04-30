"""HTTP client helpers for integration tests."""
from __future__ import annotations

import httpx

# Bypass system proxy for local service calls
_client = httpx.Client(transport=httpx.HTTPTransport())


def post(base_url: str, path: str, json: dict, timeout: float = 10.0) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    resp = _client.post(url, json=json, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def post_response(base_url: str, path: str, json: dict, timeout: float = 10.0) -> httpx.Response:
    url = f"{base_url.rstrip('/')}{path}"
    return _client.post(url, json=json, timeout=timeout)


def get(base_url: str, path: str, timeout: float = 10.0) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    resp = _client.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def put(base_url: str, path: str, json: dict, timeout: float = 10.0) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    resp = _client.put(url, json=json, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def delete(base_url: str, path: str, timeout: float = 10.0) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    resp = _client.delete(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()
