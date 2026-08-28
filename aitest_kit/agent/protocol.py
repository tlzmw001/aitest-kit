"""Versioned JSONL protocol shared by the Python control plane and Pi Worker."""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, Mapping


PROTOCOL_VERSION = 1
SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
}
_SECRET_VALUE_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[^\s\"']+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}"),
)


class ProtocolError(RuntimeError):
    """Raised when a JSONL message violates the AITest protocol."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def redact(value: Any) -> Any:
    """Return a JSON-safe copy with credential-shaped values removed."""
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for raw_key, child in value.items():
            key = str(raw_key)
            normalized = key.lower().replace("-", "_")
            redacted[key] = "[REDACTED]" if normalized in SENSITIVE_KEYS else redact(child)
        return redacted
    if isinstance(value, list):
        return [redact(child) for child in value]
    if isinstance(value, tuple):
        return [redact(child) for child in value]
    if isinstance(value, str):
        rendered = value
        for pattern in _SECRET_VALUE_PATTERNS:
            rendered = pattern.sub("[REDACTED]", rendered)
        return rendered
    return value


@dataclass(frozen=True)
class ProtocolMessage:
    protocol_version: int
    id: str
    type: str
    payload: dict[str, Any]

    @classmethod
    def create(
        cls,
        message_type: str,
        payload: Mapping[str, Any] | None = None,
        *,
        message_id: str | None = None,
    ) -> "ProtocolMessage":
        if not message_type:
            raise ProtocolError("INVALID_ENVELOPE", "message type must be a non-empty string")
        return cls(
            protocol_version=PROTOCOL_VERSION,
            id=message_id or str(uuid.uuid4()),
            type=message_type,
            payload=dict(payload or {}),
        )
    @classmethod
    def from_line(cls, line: str) -> "ProtocolMessage":
        try:
            raw = json.loads(line)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ProtocolError("INVALID_JSON", "worker output is not valid JSON") from exc
        if not isinstance(raw, dict):
            raise ProtocolError("INVALID_ENVELOPE", "protocol message must be a JSON object")
        version = raw.get("protocol_version")
        if version != PROTOCOL_VERSION:
            raise ProtocolError(
                "UNSUPPORTED_PROTOCOL_VERSION",
                f"unsupported protocol version: {version!r}",
            )
        message_id = raw.get("id")
        message_type = raw.get("type")
        payload = raw.get("payload")
        if (
            not isinstance(message_id, str)
            or not message_id
            or not isinstance(message_type, str)
            or not message_type
            or not isinstance(payload, dict)
        ):
            raise ProtocolError("INVALID_ENVELOPE", "protocol envelope fields are invalid")
        return cls(version, message_id, message_type, payload)

    def to_line(self) -> str:
        return json.dumps(
            {
                "protocol_version": self.protocol_version,
                "id": self.id,
                "type": self.type,
                "payload": redact(self.payload),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
