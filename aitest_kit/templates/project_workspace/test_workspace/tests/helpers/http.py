"""HTTP helper functions for generated tests."""
from __future__ import annotations

import httpx


_client = httpx.Client(transport=httpx.HTTPTransport())


def post(base_url: str, path: str, json: dict, timeout: float = 10.0) -> dict:
    response = post_response(base_url, path, json=json, timeout=timeout)
    response.raise_for_status()
    return response.json()


def post_response(base_url: str, path: str, json: dict, timeout: float = 10.0) -> httpx.Response:
    url = f"{base_url.rstrip('/')}{path}"
    return _client.post(url, json=json, timeout=timeout)


def get(base_url: str, path: str, timeout: float = 10.0) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    response = _client.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def put(base_url: str, path: str, json: dict, timeout: float = 10.0) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    response = _client.put(url, json=json, timeout=timeout)
    response.raise_for_status()
    return response.json()


def delete(base_url: str, path: str, timeout: float = 10.0) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    response = _client.delete(url, timeout=timeout)
    response.raise_for_status()
    return response.json()

