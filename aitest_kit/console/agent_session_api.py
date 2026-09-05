"""Authenticated HTTP and SSE surface for local Agent sessions."""
from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from aitest_kit.console.errors import ConsoleError


MAX_PROMPT_BYTES = 64 * 1024


class CreateAgentSessionRequest(BaseModel):
    permission_mode: str
    confirmed: bool = False


class ActivateAgentSessionRequest(BaseModel):
    confirmed: bool = False


class AgentMessageRequest(BaseModel):
    text: str = Field(max_length=MAX_PROMPT_BYTES)


class AgentApprovalRequest(BaseModel):
    decision: str


class AgentSessionProtocol(Protocol):
    session_id: str
    events: Any

    def snapshot(self) -> dict[str, Any]: ...
    def event_replay(self, after_seq: int) -> dict[str, Any]: ...
    def send_message(self, text: str) -> dict[str, Any]: ...
    def resolve_approval(self, request_id: str, decision: str) -> dict[str, Any]: ...
    def abort(self) -> dict[str, Any]: ...


class AgentSessionManagerProtocol(Protocol):
    def create(self, permission_mode: str, *, confirmed: bool) -> dict[str, Any]: ...
    def list_sessions(self) -> list[dict[str, Any]]: ...
    def snapshot(self) -> dict[str, Any] | None: ...
    def get(self, session_id: str) -> dict[str, Any]: ...
    def history(self, session_id: str, *, after_seq: int) -> dict[str, Any]: ...
    def activate(self, session_id: str, *, confirmed: bool) -> dict[str, Any]: ...
    def require(self, session_id: str) -> AgentSessionProtocol: ...
    def archive(self, session_id: str) -> None: ...


def create_agent_session_router(manager: AgentSessionManagerProtocol) -> APIRouter:
    router = APIRouter(prefix="/api/agent")

    @router.post("/sessions")
    async def create_session(payload: CreateAgentSessionRequest, response: Response) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return manager.create(payload.permission_mode, confirmed=payload.confirmed)

    @router.get("/sessions")
    async def list_sessions(response: Response) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return {"sessions": manager.list_sessions()}

    @router.get("/session")
    async def get_session(response: Response) -> Optional[dict[str, Any]]:
        response.headers["Cache-Control"] = "no-store"
        return manager.snapshot()

    @router.get("/sessions/{session_id}")
    async def get_stored_session(session_id: str, response: Response) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return manager.get(session_id)

    @router.get("/sessions/{session_id}/history")
    async def session_history(session_id: str, response: Response, after_seq: int = 0) -> dict[str, Any]:
        if after_seq < 0:
            raise ConsoleError("AGENT_EVENT_CURSOR_INVALID", "after_seq 不能小于 0", status_code=422)
        response.headers["Cache-Control"] = "no-store"
        return manager.history(session_id, after_seq=after_seq)

    @router.post("/sessions/{session_id}/activate")
    async def activate_session(
        session_id: str,
        payload: ActivateAgentSessionRequest,
        response: Response,
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return manager.activate(session_id, confirmed=payload.confirmed)

    @router.post("/sessions/{session_id}/messages")
    async def send_message(session_id: str, payload: AgentMessageRequest, response: Response) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return manager.require(session_id).send_message(payload.text)

    @router.post("/sessions/{session_id}/approvals/{request_id}")
    async def approve(session_id: str, request_id: str, payload: AgentApprovalRequest, response: Response) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return manager.require(session_id).resolve_approval(request_id, payload.decision)

    @router.post("/sessions/{session_id}/abort")
    async def abort(session_id: str, response: Response) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return manager.require(session_id).abort()

    @router.delete("/sessions/{session_id}", status_code=204)
    async def delete_session(session_id: str) -> Response:
        manager.archive(session_id)
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    @router.post("/sessions/{session_id}/archive", status_code=204)
    async def archive_session(session_id: str) -> Response:
        manager.archive(session_id)
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    @router.get("/sessions/{session_id}/events")
    async def session_events(session_id: str, request: Request, after_seq: int = 0) -> StreamingResponse:
        if after_seq < 0:
            raise ConsoleError("AGENT_EVENT_CURSOR_INVALID", "after_seq 不能小于 0", status_code=422)
        session = manager.require(session_id)
        return StreamingResponse(
            _stream_events(session, request, after_seq),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    return router


async def _stream_events(session: AgentSessionProtocol, request: Request, after_seq: int) -> Iterator[str]:
    cursor = after_seq
    closed = False
    while True:
        replay = session.event_replay(cursor)
        if replay["resync_required"]:
            cursor = replay["session"]["last_seq"]
            yield _encode_sse({
                "event_id": str(uuid.uuid4()), "seq": cursor,
                "session_id": session.session_id, "type": "resync_required",
                "timestamp": _now(), "correlation_id": "",
                "payload": {key: replay[key] for key in ("session", "events", "pending_approvals")},
            })
        else:
            for event in replay["events"]:
                yield _encode_sse(event)
                cursor = event["seq"]
        if closed or await request.is_disconnected():
            return
        events, closed = await asyncio.to_thread(session.events.wait_after, cursor, 15.0)
        if not events and not closed:
            yield ": heartbeat\n\n"


def _encode_sse(event: Mapping[str, Any]) -> str:
    data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    return f"id: {event['seq']}\nevent: {event['type']}\ndata: {data}\n\n"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
