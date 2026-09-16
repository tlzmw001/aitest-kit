"""Bounded diagnostic projection independent of the live SSE replay window."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping


class DiagnosticProjection:
    def __init__(self, events: Iterable[Mapping[str, Any]] = ()) -> None:
        self._requests: dict[str, dict[str, Any]] = {}
        self._retry: dict[str, Any] | None = None
        self._message_id = ""
        for event in events:
            self.apply(str(event["type"]), event["payload"], str(event.get("correlation_id", "")))

    def apply(self, event_type: str, payload: Mapping[str, Any], correlation_id: str = "") -> None:
        if event_type == "request_diagnostic" and isinstance(payload.get("request_id"), str):
            self._requests[payload["request_id"]] = deepcopy(dict(payload))
            self._message_id = str(payload.get("message_id", ""))
            if payload.get("phase") == "preparing" and self._retry:
                self._retry["waiting"] = False
            while len(self._requests) > 20:
                del self._requests[next(iter(self._requests))]
        elif event_type == "agent_retry":
            self._retry = {**deepcopy(dict(payload)), "waiting": payload.get("phase") == "start"}
        elif event_type == "user_message":
            self._retry = None
            self._message_id = correlation_id

    def snapshot(self) -> dict[str, Any]:
        return deepcopy({"requests": list(self._requests.values()), "retry": self._retry, "message_id": self._message_id})
