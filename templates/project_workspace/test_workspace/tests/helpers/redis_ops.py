"""Redis operations with automatic key tracking and cleanup."""
from __future__ import annotations

import redis


class RedisTracker:
    """Wraps redis.Redis, tracks written keys, and cleans them up on close."""

    def __init__(self, url: str):
        self._client = redis.Redis.from_url(url, decode_responses=True)
        self._tracked_keys: set[str] = set()

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._client.set(key, value, ex=ex)
        self._tracked_keys.add(key)

    def get(self, key: str) -> str | None:
        return self._client.get(key)

    def delete(self, *keys: str) -> None:
        if keys:
            self._client.delete(*keys)
            self._tracked_keys -= set(keys)

    def exists(self, key: str) -> bool:
        return bool(self._client.exists(key))

    def cleanup(self) -> None:
        if self._tracked_keys:
            self._client.delete(*self._tracked_keys)
            self._tracked_keys.clear()

    def close(self) -> None:
        self.cleanup()
        self._client.close()
