"""Thread-safe in-memory replay plus a redacted append-only Agent event journal."""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from aitest_kit.agent.protocol import redact


MAX_EVENT_COUNT = 1000
MAX_EVENT_BYTES = 2 * 1024 * 1024
_LOGGER = logging.getLogger(__name__)
_OMITTED_DIFF_FIELDS = {"content", "old_text", "new_text", "oldText", "newText"}


@dataclass(frozen=True)
class ReplayResult:
    events: list[dict[str, Any]]
    resync_required: bool


class AgentEventLog:
    def __init__(self, *, journal_path: str | Path | None = None) -> None:
        self._events: deque[tuple[dict[str, Any], int]] = deque()
        self._bytes = 0
        self._last_seq = 0
        self._closed = False
        self._condition = threading.Condition()
        self._journal_path = Path(journal_path).resolve(strict=False) if journal_path else None
        if self._journal_path is not None:
            self._load_journal()

    @property
    def last_seq(self) -> int:
        with self._condition:
            return self._last_seq

    def append(
        self,
        session_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        correlation_id: str = "",
    ) -> dict[str, Any]:
        with self._condition:
            self._last_seq += 1
            event = {
                "event_id": str(uuid.uuid4()),
                "seq": self._last_seq,
                "session_id": session_id,
                "type": event_type,
                "timestamp": _now(),
                "correlation_id": correlation_id,
                "payload": redact(dict(payload)),
            }
            self._remember(event)
            self._persist(event)
            self._condition.notify_all()
            return dict(event)

    def replay(self, after_seq: int) -> ReplayResult:
        with self._condition:
            oldest = self._events[0][0]["seq"] if self._events else self._last_seq + 1
            required = bool(self._events and after_seq < oldest - 1)
            return ReplayResult(
                events=[dict(event) for event, _ in self._events if event["seq"] > after_seq],
                resync_required=required,
            )

    def wait_after(self, after_seq: int, timeout: float) -> tuple[list[dict[str, Any]], bool]:
        with self._condition:
            if self._last_seq <= after_seq and not self._closed:
                self._condition.wait(timeout)
            return (
                [dict(event) for event, _ in self._events if event["seq"] > after_seq],
                self._closed,
            )

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    def _remember(self, event: dict[str, Any]) -> None:
        size = len(_serialize(event).encode("utf-8"))
        self._events.append((event, size))
        self._bytes += size
        while len(self._events) > MAX_EVENT_COUNT or self._bytes > MAX_EVENT_BYTES:
            _, removed = self._events.popleft()
            self._bytes -= removed

    def _persist(self, event: dict[str, Any]) -> None:
        if self._journal_path is None:
            return
        self._journal_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            self._journal_path.parent.chmod(0o700)
        except OSError:
            pass
        persisted = _persistent_event(event)
        descriptor = os.open(self._journal_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
            handle.write(_serialize(persisted) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            self._journal_path.chmod(0o600)
        except OSError:
            pass

    def _load_journal(self) -> None:
        if self._journal_path is None or not self._journal_path.exists():
            return
        try:
            content = self._journal_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ValueError(f"cannot read Agent event journal: {exc}") from exc
        lines = content.splitlines(keepends=True)
        for index, line in enumerate(lines):
            raw = line.rstrip("\r\n")
            if not raw:
                continue
            try:
                event = json.loads(raw)
                _validate_event(event, previous_seq=self._last_seq)
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                is_incomplete_tail = index == len(lines) - 1 and not line.endswith(("\n", "\r"))
                if is_incomplete_tail:
                    _LOGGER.warning("Ignoring incomplete final Agent event journal line: %s", self._journal_path)
                    break
                raise ValueError(f"invalid Agent event journal at line {index + 1}") from exc
            self._last_seq = int(event["seq"])
            self._remember(event)


def _persistent_event(event: Mapping[str, Any]) -> dict[str, Any]:
    persisted = json.loads(_serialize(redact(dict(event))))
    payload = persisted.get("payload")
    if not isinstance(payload, dict):
        return persisted
    if persisted.get("type") == "tool_call_updated" and "partial_result" in payload:
        payload.pop("partial_result", None)
        payload["tool_output_persisted"] = False
        return persisted
    if persisted.get("type") == "tool_call_finished" and "result" in payload:
        payload.pop("result", None)
        payload["tool_output_persisted"] = False
        return persisted
    if persisted.get("type") != "tool_call_requested":
        return persisted
    tool_input = payload.get("input")
    if not isinstance(tool_input, dict):
        return persisted
    omitted = [key for key in _OMITTED_DIFF_FIELDS if key in tool_input]
    for key in omitted:
        tool_input.pop(key, None)
    if omitted:
        tool_input["diff_content_persisted"] = False
    return persisted


def _validate_event(event: Any, *, previous_seq: int) -> None:
    if not isinstance(event, dict):
        raise TypeError("event must be an object")
    required_strings = ("event_id", "session_id", "type", "timestamp", "correlation_id")
    if any(not isinstance(event.get(key), str) for key in required_strings):
        raise ValueError("event fields are invalid")
    seq = event.get("seq")
    if not isinstance(seq, int) or seq <= previous_seq:
        raise ValueError("event seq is not increasing")
    if not isinstance(event.get("payload"), dict):
        raise ValueError("event payload is invalid")


def _serialize(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
