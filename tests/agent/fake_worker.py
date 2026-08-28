from __future__ import annotations

import json
import sys


def emit(message_id: str, message_type: str, payload: dict | None = None) -> None:
    sys.stdout.write(
        json.dumps(
            {
                "protocol_version": 1,
                "id": message_id,
                "type": message_type,
                "payload": payload or {},
            }
        )
        + "\n"
    )
    sys.stdout.flush()


for raw_line in sys.stdin:
    message = json.loads(raw_line)
    message_id = message["id"]
    message_type = message["type"]
    payload = message.get("payload", {})

    if message_type == "initialize":
        emit(message_id, "ready", {"runtime": "fake", "protocol_version": 1})
    elif message_type == "prompt":
        text = payload.get("text", "")
        if text == "crash":
            raise SystemExit(23)
        if text == "hang":
            emit(message_id, "session_started", {"session_id": "fake-session"})
            continue
        if text == "error":
            emit(message_id, "error", {"code": "FAKE_ERROR", "message": "fake failure"})
            continue
        emit(message_id, "session_started", {"session_id": "fake-session"})
        emit(
            message_id,
            "tool_call_requested",
            {"tool_call_id": "tool-1", "tool_name": "write", "input": {"path": "suite.md"}},
        )
        emit(
            "permission-1",
            "permission_requested",
            {
                "request_id": "permission-1",
                "tool_call_id": "tool-1",
                "tool_name": "write",
                "cwd": payload.get("cwd", "."),
                "target": "suite.md",
            },
        )
    elif message_type == "permission_decision":
        decision = payload["decision"]
        emit(
            message_id,
            "permission_resolved",
            {"request_id": payload["request_id"], "decision": decision},
        )
        emit(
            message_id,
            "tool_call_finished",
            {"tool_call_id": "tool-1", "tool_name": "write", "is_error": decision == "deny"},
        )
        emit(message_id, "text_delta", {"delta": "done"})
        emit(message_id, "agent_finished", {"status": "succeeded"})
    elif message_type == "abort":
        emit(message_id, "aborted", {})
    elif message_type == "shutdown":
        emit(message_id, "shutdown_complete", {})
        raise SystemExit(0)
    else:
        emit(
            message_id,
            "error",
            {"code": "UNKNOWN_MESSAGE_TYPE", "message": f"unknown type: {message_type}"},
        )
