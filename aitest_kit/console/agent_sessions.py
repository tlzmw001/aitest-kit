"""In-memory Pi Agent sessions and authenticated Console transport."""
from __future__ import annotations

import asyncio
import json
import shlex
import threading
import uuid
from collections import deque
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Protocol

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from aitest_kit.agent.client import AgentWorkerError, WorkerClient, default_worker_command
from aitest_kit.agent.protocol import ProtocolMessage, redact
from aitest_kit.console.agent_connections import AgentConnectionService
from aitest_kit.console.errors import ConsoleError


MAX_EVENT_COUNT = 1000
MAX_EVENT_BYTES = 2 * 1024 * 1024
MAX_PROMPT_BYTES = 64 * 1024
TERMINAL_STATES = {"succeeded", "failed", "aborted"}
PERMISSION_DECISIONS = {"allow_once", "allow_session", "deny"}


class SessionWorker(Protocol):
    def start(self, payload: Mapping[str, Any]) -> ProtocolMessage: ...
    def read_event(self, *, timeout: float | None = None) -> ProtocolMessage: ...
    def send_prompt(self, text: str) -> str: ...
    def send_permission_decision(self, request_id: str, decision: str) -> str: ...
    def request_abort(self) -> str: ...
    def request_shutdown(self) -> str: ...
    def wait_for_exit(self, *, timeout: float | None = None) -> None: ...


WorkerFactory = Callable[[Mapping[str, str]], SessionWorker]


class CreateAgentSessionRequest(BaseModel):
    permission_mode: str
    confirmed: bool = False


class AgentMessageRequest(BaseModel):
    text: str = Field(max_length=MAX_PROMPT_BYTES)


class AgentApprovalRequest(BaseModel):
    decision: str


@dataclass(frozen=True)
class ReplayResult:
    events: list[dict[str, Any]]
    resync_required: bool


class AgentEventLog:
    def __init__(self) -> None:
        self._events: deque[tuple[dict[str, Any], int]] = deque()
        self._bytes = 0
        self._last_seq = 0
        self._closed = False
        self._condition = threading.Condition()

    @property
    def last_seq(self) -> int:
        with self._condition:
            return self._last_seq

    def append(self, session_id: str, event_type: str, payload: Mapping[str, Any], correlation_id: str = "") -> dict[str, Any]:
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
            size = len(json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            self._events.append((event, size))
            self._bytes += size
            while len(self._events) > MAX_EVENT_COUNT or self._bytes > MAX_EVENT_BYTES:
                _, removed = self._events.popleft()
                self._bytes -= removed
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


class AgentSession:
    def __init__(
        self,
        *,
        workspace: Path,
        permission_mode: str,
        worker: SessionWorker,
        initialize_payload: Mapping[str, Any],
    ) -> None:
        self.session_id = str(uuid.uuid4())
        self.workspace = workspace.resolve()
        self.permission_mode = permission_mode
        self.worker = worker
        self.events = AgentEventLog()
        self.status = "created"
        self.pi_session_id = ""
        self.active_prompt = False
        self.pending_approvals: dict[str, dict[str, Any]] = {}
        self.created_at = _now()
        self.updated_at = self.created_at
        self._lock = threading.RLock()
        self._closing = False
        self._terminal_emitted = False
        ready = worker.start(initialize_payload)
        self.pi_session_id = str(ready.payload.get("session_id") or "")
        self._reader = threading.Thread(target=self._read_worker, name="aitest-console-agent", daemon=True)
        self._reader.start()
        self._append("session_created", {"permission_mode": permission_mode})

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "session_id": self.session_id,
                "pi_session_id": self.pi_session_id,
                "permission_mode": self.permission_mode,
                "status": self.status,
                "active_prompt": self.active_prompt,
                "pending_approval_ids": list(self.pending_approvals),
                "last_seq": self.events.last_seq,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }

    def send_message(self, text: str) -> dict[str, Any]:
        normalized = text.strip()
        if not normalized:
            raise ConsoleError("AGENT_PROMPT_REQUIRED", "请输入消息", status_code=422)
        if len(normalized.encode("utf-8")) > MAX_PROMPT_BYTES:
            raise ConsoleError("AGENT_PROMPT_TOO_LARGE", "Agent 消息不能超过 64 KiB", status_code=413)
        with self._lock:
            if self.active_prompt:
                raise ConsoleError("AGENT_PROMPT_ALREADY_RUNNING", "当前 Agent 正在处理上一条消息", status_code=409)
            message_id = self.worker.send_prompt(normalized)
            self.active_prompt = True
            self._terminal_emitted = False
            self.status = "running"
            self._append("user_message", {"text": normalized}, message_id)
            return self.snapshot()

    def resolve_approval(self, request_id: str, decision: str) -> dict[str, Any]:
        if self.permission_mode == "full_trust":
            raise ConsoleError("AGENT_APPROVAL_NOT_ALLOWED", "完全信任模式不接受逐次审批", status_code=409)
        if decision not in PERMISSION_DECISIONS:
            raise ConsoleError("AGENT_APPROVAL_INVALID", "审批决定不受支持", status_code=422)
        with self._lock:
            if request_id not in self.pending_approvals:
                raise ConsoleError("AGENT_APPROVAL_NOT_PENDING", "审批请求不存在或已经处理", status_code=409)
            self.worker.send_permission_decision(request_id, decision)
            del self.pending_approvals[request_id]
            self.status = "awaiting_approval" if self.pending_approvals else "running"
            self._append("approval_submitted", {"request_id": request_id, "decision": decision})
            return self.snapshot()

    def abort(self) -> dict[str, Any]:
        with self._lock:
            if not self.active_prompt and self.status == "aborted":
                return self.snapshot()
            self.worker.request_abort()
            return self.snapshot()

    def close(self) -> None:
        with self._lock:
            if self._closing:
                return
            self._closing = True
            try:
                self.worker.request_shutdown()
            except AgentWorkerError:
                pass
        self.worker.wait_for_exit(timeout=5)
        self._reader.join(timeout=1)
        self.events.close()

    def _read_worker(self) -> None:
        while True:
            try:
                event = self.worker.read_event(timeout=0.5)
            except AgentWorkerError as exc:
                if exc.code == "WORKER_TIMEOUT" and not self._closing:
                    continue
                if not self._closing:
                    self._fail(exc.code, str(exc))
                return
            if event.type == "shutdown_complete":
                return
            self._handle_worker_event(event)

    def _handle_worker_event(self, event: ProtocolMessage) -> None:
        with self._lock:
            payload = dict(event.payload)
            if event.type == "session_started":
                self.pi_session_id = str(payload.get("session_id") or self.pi_session_id)
            if event.type == "permission_requested":
                if not _valid_permission(payload) or self.permission_mode != "approval":
                    request_id = str(payload.get("request_id") or event.id)
                    try:
                        self.worker.send_permission_decision(request_id, "deny")
                    except AgentWorkerError:
                        pass
                    self._append("permission_invalid", {"request_id": request_id, "reason": "incomplete permission request"}, event.id)
                    return
                request_id = str(payload["request_id"])
                self.pending_approvals[request_id] = payload
                self.status = "awaiting_approval"
            elif event.type == "permission_resolved":
                self.pending_approvals.pop(str(payload.get("request_id") or ""), None)
                self.status = "awaiting_approval" if self.pending_approvals else "running"
            elif event.type == "agent_finished":
                if self._terminal_emitted:
                    return
                status = str(payload.get("status") or "failed")
                self.status = status if status in TERMINAL_STATES else "failed"
                self.active_prompt = False
                self.pending_approvals.clear()
                self._terminal_emitted = True
            elif event.type == "aborted":
                was_active = self.active_prompt
                self.status = "aborted"
                self.active_prompt = False
                self.pending_approvals.clear()
                self._append(event.type, _enrich_paths(self.workspace, event.type, payload), event.id)
                if was_active and not self._terminal_emitted:
                    self._terminal_emitted = True
                    self._append("agent_finished", {"status": "aborted"}, event.id)
                return
            elif event.type == "error":
                was_active = self.active_prompt
                self.status = "failed"
                self.active_prompt = False
                self.pending_approvals.clear()
                self._append(event.type, _enrich_paths(self.workspace, event.type, payload), event.id)
                if was_active and not self._terminal_emitted:
                    self._terminal_emitted = True
                    self._append("agent_finished", {"status": "failed"}, event.id)
                return
            self._append(event.type, _enrich_paths(self.workspace, event.type, payload), event.id)

    def _fail(self, code: str, message: str) -> None:
        with self._lock:
            self.status = "failed"
            was_active = self.active_prompt
            self.active_prompt = False
            self.pending_approvals.clear()
            self._append("error", {"code": code, "message": message})
            if was_active:
                self._terminal_emitted = True
                self._append("agent_finished", {"status": "failed"})

    def _append(self, event_type: str, payload: Mapping[str, Any], correlation_id: str = "") -> None:
        self.updated_at = _now()
        self.events.append(self.session_id, event_type, payload, correlation_id)


class AgentSessionManager:
    def __init__(
        self,
        connections: AgentConnectionService,
        workspace_root: Callable[[], Path],
        worker_factory: WorkerFactory | None = None,
    ) -> None:
        self._connections = connections
        self._workspace_root = workspace_root
        self._worker_factory = worker_factory or (
            lambda environment: WorkerClient(default_worker_command(), env=environment)
        )
        self._current: AgentSession | None = None
        self._lock = threading.RLock()

    def create(self, permission_mode: str, *, confirmed: bool) -> dict[str, Any]:
        if permission_mode not in {"approval", "full_trust"}:
            raise ConsoleError("AGENT_PERMISSION_MODE_INVALID", "权限模式不受支持", status_code=422)
        if permission_mode == "full_trust" and not confirmed:
            raise ConsoleError(
                "FULL_TRUST_CONFIRMATION_REQUIRED",
                "完全信任模式继承本地权限，文件内容可能进入模型上下文，需要明确确认",
                status_code=403,
            )
        with self._lock:
            self.close()
            workspace = self._workspace_root().resolve()
            launch = self._connections.runtime_launch(workspace, permission_mode=permission_mode)
            worker = self._worker_factory(launch.environment)
            try:
                self._current = AgentSession(
                    workspace=workspace,
                    permission_mode=permission_mode,
                    worker=worker,
                    initialize_payload=launch.initialize_payload,
                )
            except AgentWorkerError as exc:
                raise ConsoleError(exc.code, str(exc), status_code=502) from exc
            return self._current.snapshot()

    def snapshot(self) -> dict[str, Any] | None:
        with self._lock:
            return self._current.snapshot() if self._current else None

    def require(self, session_id: str) -> AgentSession:
        with self._lock:
            if not self._current or self._current.session_id != session_id:
                raise ConsoleError("AGENT_SESSION_NOT_FOUND", "Agent session 不存在", status_code=404)
            return self._current

    def close(self, session_id: str | None = None) -> None:
        with self._lock:
            if session_id is not None:
                self.require(session_id)
            current = self._current
            self._current = None
        if current:
            current.close()


def create_agent_session_router(manager: AgentSessionManager) -> APIRouter:
    router = APIRouter(prefix="/api/agent")

    @router.post("/sessions")
    async def create_session(payload: CreateAgentSessionRequest, response: Response) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return manager.create(payload.permission_mode, confirmed=payload.confirmed)

    @router.get("/session")
    async def get_session(response: Response) -> Optional[dict[str, Any]]:
        response.headers["Cache-Control"] = "no-store"
        return manager.snapshot()

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
        manager.close(session_id)
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


async def _stream_events(session: AgentSession, request: Request, after_seq: int) -> Iterator[str]:
    cursor = after_seq
    replay = session.events.replay(cursor)
    if replay.resync_required:
        yield _encode_sse({
            "event_id": str(uuid.uuid4()),
            "seq": session.events.last_seq,
            "session_id": session.session_id,
            "type": "resync_required",
            "timestamp": _now(),
            "correlation_id": "",
            "payload": {"session": session.snapshot()},
        })
        cursor = session.events.last_seq
    else:
        for event in replay.events:
            yield _encode_sse(event)
            cursor = event["seq"]
    while not await request.is_disconnected():
        events, closed = await asyncio.to_thread(session.events.wait_after, cursor, 15.0)
        for event in events:
            yield _encode_sse(event)
            cursor = event["seq"]
        if closed:
            return
        if not events:
            yield ": heartbeat\n\n"


def _encode_sse(event: Mapping[str, Any]) -> str:
    data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    return f"id: {event['seq']}\nevent: {event['type']}\ndata: {data}\n\n"


def _valid_permission(payload: Mapping[str, Any]) -> bool:
    request_id = payload.get("request_id")
    tool_name = payload.get("tool_name")
    surface = payload.get("surface")
    target = payload.get("command") if surface == "bash" else payload.get("target")
    return all(isinstance(value, str) and bool(value) for value in (request_id, tool_name, target))


def _enrich_paths(workspace: Path, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    if event_type == "tool_call_requested" and isinstance(payload.get("input"), dict):
        tool_input = dict(payload["input"])
        raw_path = tool_input.get("path")
        if isinstance(raw_path, str):
            try:
                candidate = Path(raw_path)
                resolved = (workspace / candidate).resolve(strict=False) if not candidate.is_absolute() else candidate.resolve(strict=False)
                relative = resolved.relative_to(workspace)
                tool_input["workspace_path"] = relative.as_posix()
            except (OSError, ValueError):
                pass
        payload["input"] = tool_input
        command = tool_input.get("command")
        if isinstance(command, str):
            operation = _aitest_operation(command)
            if operation:
                payload["aitest_operation"] = operation
    return payload


def _aitest_operation(command: str) -> str | None:
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    for index, part in enumerate(parts):
        if Path(part).name == "aitest" and index + 1 < len(parts):
            return parts[index + 1] if parts[index + 1] in {"codegen", "run", "report"} else None
        if parts[index:index + 3] in (["python", "-m", "aitest_kit.cli"], ["python3", "-m", "aitest_kit.cli"]):
            operation_index = index + 3
            return parts[operation_index] if operation_index < len(parts) and parts[operation_index] in {"codegen", "run", "report"} else None
    return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
