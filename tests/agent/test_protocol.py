from __future__ import annotations

import json

import pytest

from aitest_kit.agent.protocol import PROTOCOL_VERSION, ProtocolError, ProtocolMessage


def test_protocol_message_round_trip() -> None:
    message = ProtocolMessage.create("initialize", {"cwd": "/tmp/workspace"}, message_id="m-1")

    decoded = ProtocolMessage.from_line(message.to_line())

    assert decoded.protocol_version == PROTOCOL_VERSION
    assert decoded.id == "m-1"
    assert decoded.type == "initialize"
    assert decoded.payload == {"cwd": "/tmp/workspace"}


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("not-json", "INVALID_JSON"),
        (json.dumps({"protocol_version": 2, "id": "m", "type": "ready", "payload": {}}), "UNSUPPORTED_PROTOCOL_VERSION"),
        (json.dumps({"protocol_version": 1, "id": "", "type": "ready", "payload": {}}), "INVALID_ENVELOPE"),
        (json.dumps({"protocol_version": 1, "id": "m", "type": "ready", "payload": []}), "INVALID_ENVELOPE"),
    ],
)
def test_protocol_rejects_invalid_lines(raw: str, code: str) -> None:
    with pytest.raises(ProtocolError) as exc_info:
        ProtocolMessage.from_line(raw)

    assert exc_info.value.code == code


def test_redaction_never_serializes_secret_values() -> None:
    message = ProtocolMessage.create(
        "error",
        {
            "api_key": "sk-secret-value",
            "authorization": "Bearer secret-token",
            "nested": {"password": "dont-log-me", "safe": "visible"},
        },
        message_id="m-2",
    )

    rendered = message.to_line()

    assert "sk-secret-value" not in rendered
    assert "secret-token" not in rendered
    assert "dont-log-me" not in rendered
    assert "visible" in rendered
