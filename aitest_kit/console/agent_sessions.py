"""Persistent Pi Agent session lifecycle for the local Console."""
from __future__ import annotations

import shlex
import logging
import threading
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from aitest_kit.agent.client import AgentWorkerError, WorkerClient, default_worker_command
from aitest_kit.agent.protocol import ProtocolMessage, redact
from aitest_kit.console.agent_connections import AgentConnectionService
from aitest_kit.console.agent_event_log import AgentEventLog
from aitest_kit.console.agent_session_store import AgentSessionRecord, AgentSessionStore
from aitest_kit.console.agent_session_recovery import recover_session, session_write_lease
from aitest_kit.console.agent_worker_lease import AgentWorkerLease
from aitest_kit.console.errors import ConsoleError


MAX_PROMPT_BYTES = 64 * 1024
TERMINAL_STATES = {"succeeded", "failed", "aborted"}
PERMISSION_DECISIONS = {"allow_once", "allow_session", "deny"}
_LOGGER = logging.getLogger(__name__)


class SessionWorker(Protocol):
    def start(self, payload: Mapping[str, Any]) -> ProtocolMessage: ...
    def read_event(self, *, timeout: float | None = None) -> ProtocolMessage: ...
    def send_prompt(self, text: str) -> str: ...
    def send_permission_decision(self, request_id: str, decision: str) -> str: ...
    def request_abort(self) -> str: ...
    def request_shutdown(self) -> str: ...
    def wait_for_exit(self, *, timeout: float | None = None) -> None: ...


WorkerFactory = Callable[[Mapping[str, str]], SessionWorker]


class AgentSession:
    def __init__(
        self,
        *,
        workspace: Path,
        record: AgentSessionRecord,
        store: AgentSessionStore,
        worker: SessionWorker,
        initialize_payload: Mapping[str, Any],
        resumed: bool,
    ) -> None:
        self.session_id = record.session_id
        self.workspace = workspace.resolve()
        self.permission_mode = record.permission_mode
        self.title = record.title
        self._record = record
        self._store = store
        self.worker = worker
        self.events = AgentEventLog(journal_path=store.event_path(self.workspace, self.session_id))
        self.status = record.status
        self.pi_session_id = record.pi_session_id
        self.active_prompt = False
        self.pending_approvals: dict[str, dict[str, Any]] = {}
        self.created_at = record.created_at
        self.updated_at = record.updated_at
        self._lock = threading.RLock()
        self._closing = False
        self._terminal_emitted = False
        ready = worker.start(initialize_payload)
        self.pi_session_id = str(ready.payload.get("session_id") or "")
        self._store.set_pi_session_file(record, str(ready.payload.get("session_file") or ""))
        self._reader = threading.Thread(target=self._read_worker, name="aitest-console-agent", daemon=True)
        self._append(
            "session_resumed" if resumed else "session_created",
            {"permission_mode": self.permission_mode},
        )
        self._reader.start()

    def event_replay(self, after_seq: int) -> dict[str, Any]:
        with self._lock:
            replay = self.events.replay(after_seq)
            return {
                "events": replay.events,
                "resync_required": replay.resync_required,
                "session": self.snapshot(),
                "pending_approvals": list(self.pending_approvals.values()),
            }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "session_id": self.session_id,
                "pi_session_id": self.pi_session_id,
                "permission_mode": self.permission_mode,
                "title": self.title,
                "status": self.status,
                "active_prompt": self.active_prompt,
                "pending_approval_ids": list(self.pending_approvals),
                "last_seq": self.events.last_seq,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "is_active": True,
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
            if self.title == "新会话":
                self.title = _session_title(normalized)
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
            was_active = self.active_prompt or bool(self.pending_approvals)
            try:
                self.worker.request_shutdown()
            except AgentWorkerError:
                pass
        self.worker.wait_for_exit(timeout=5)
        self._reader.join(timeout=1)
        with self._lock:
            if was_active:
                self.status = "interrupted"
                self.active_prompt = False
                self.pending_approvals.clear()
                self._append(
                    "session_interrupted",
                    {"reason": "runtime_stopped", "tool_result_unknown": True},
                )
            else:
                self._persist()
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
        self._persist()

    def _persist(self) -> None:
        self._record.pi_session_id = self.pi_session_id
        self._record.permission_mode = self.permission_mode
        self._record.title = self.title
        self._record.status = self.status
        self._record.active_prompt = self.active_prompt
        self._record.pending_approval_ids = list(self.pending_approvals)
        self._record.last_seq = self.events.last_seq
        self._record.updated_at = self.updated_at
        self._store.save(self._record)


class AgentSessionManager:
    def __init__(
        self,
        connections: AgentConnectionService,
        workspace_root: Callable[[], Path],
        worker_factory: WorkerFactory | None = None,
        *,
        session_home: str | Path | None = None,
    ) -> None:
        self._connections = connections
        self._workspace_root = workspace_root
        self._worker_factory = worker_factory or (
            lambda environment: WorkerClient(default_worker_command(), env=environment)
        )
        self._store = AgentSessionStore(session_home)
        self._current: AgentSession | None = None
        self._worker_lease: AgentWorkerLease | None = None
        self._lock = threading.RLock()

    def create(self, permission_mode: str, *, confirmed: bool) -> dict[str, Any]:
        with self._lock:
            self._validate_mode(permission_mode, confirmed=confirmed)
            self._deactivate(require_idle=True)
            workspace = self._workspace_root().resolve()
            record = self._store.create(workspace, permission_mode)
            try:
                return self._start(record, confirmed=confirmed, resumed=False)
            except Exception:
                self._store.remove_new(workspace, record.session_id)
                raise

    def activate(self, session_id: str, *, confirmed: bool) -> dict[str, Any]:
        with self._lock:
            if self._current and self._current.session_id == session_id:
                return self._current.snapshot()
            workspace = self._workspace_root().resolve()
            record = self._store.load(workspace, session_id)
            return self._start(record, confirmed=confirmed, resumed=True)

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            workspace = self._workspace_root().resolve()
            current_id = self._current.session_id if self._current else ""
            snapshots: list[dict[str, Any]] = []
            for record in self._store.list(workspace):
                if self._current and record.session_id == current_id:
                    snapshots.append(self._current.snapshot())
                    continue
                recovered = self._recover(record)
                snapshots.append(recovered.snapshot(is_active=recovered.session_id == current_id))
            return snapshots

    def get(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            if self._current and self._current.session_id == session_id:
                return self._current.snapshot()
            workspace = self._workspace_root().resolve()
            record = self._recover(self._store.load(workspace, session_id))
            return record.snapshot(is_active=False)

    def history(self, session_id: str, *, after_seq: int) -> dict[str, Any]:
        with self._lock:
            if self._current and self._current.session_id == session_id:
                replay = self._current.event_replay(after_seq)
                return {**replay, "last_seq": replay["session"]["last_seq"]}
            else:
                workspace = self._workspace_root().resolve()
                record = self._recover(self._store.load(workspace, session_id))
                events = AgentEventLog(journal_path=self._store.event_path(workspace, record.session_id))
            replay = events.replay(after_seq)
            return {
                "events": replay.events,
                "last_seq": events.last_seq,
                "resync_required": replay.resync_required,
                "session": record.snapshot(is_active=False),
            }

    def archive(self, session_id: str) -> None:
        with self._lock:
            workspace = self._workspace_root().resolve()
            if self._current and self._current.session_id == session_id:
                self._deactivate(require_idle=True)
            with session_write_lease(self._store, workspace, self._worker_lease):
                self._store.archive(workspace, session_id)

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
            self._deactivate(require_idle=False)

    def ensure_switch_allowed(self) -> None:
        with self._lock:
            if self._current and (self._current.active_prompt or self._current.pending_approvals):
                raise ConsoleError("AGENT_SESSION_BUSY", "Agent 运行期间不能切换 workspace", status_code=409)

    def _start(self, record: AgentSessionRecord, *, confirmed: bool, resumed: bool) -> dict[str, Any]:
        self._validate_mode(record.permission_mode, confirmed=confirmed)
        self._deactivate(require_idle=True)
        workspace = self._workspace_root().resolve()
        lease = self._store.worker_lease(workspace)
        lease.acquire()
        worker = None
        try:
            record = recover_session(self._store, self._store.load(workspace, record.session_id), lease)
            launch = self._connections.runtime_launch(workspace, permission_mode=record.permission_mode)
            payload = dict(launch.initialize_payload)
            payload["session_dir"] = str(self._store.pi_dir(workspace, record.session_id))
            session_file = self._store.resolve_pi_session_file(record)
            if session_file is not None and session_file.is_file():
                payload["session_file"] = str(session_file)
            worker = self._worker_factory(launch.environment)
            self._current = AgentSession(
                workspace=workspace,
                record=record,
                store=self._store,
                worker=worker,
                initialize_payload=payload,
                resumed=resumed,
            )
            self._worker_lease = lease
        except BaseException as exc:
            if worker is not None:
                try:
                    worker.request_shutdown()
                except AgentWorkerError:
                    _LOGGER.warning("Worker shutdown request failed during session initialization cleanup")
                worker.wait_for_exit(timeout=5)
            lease.release()
            if isinstance(exc, AgentWorkerError):
                raise ConsoleError(exc.code, str(exc), status_code=502) from exc
            raise
        return self._current.snapshot()

    @staticmethod
    def _validate_mode(permission_mode: str, *, confirmed: bool) -> None:
        if permission_mode not in {"approval", "full_trust"}:
            raise ConsoleError("AGENT_PERMISSION_MODE_INVALID", "权限模式不受支持", status_code=422)
        if permission_mode == "full_trust" and not confirmed:
            raise ConsoleError(
                "FULL_TRUST_CONFIRMATION_REQUIRED",
                "完全信任模式继承本地权限，文件内容可能进入模型上下文，需要明确确认",
                status_code=403,
            )

    def _recover(self, record: AgentSessionRecord) -> AgentSessionRecord:
        return recover_session(self._store, record, self._worker_lease)

    def _deactivate(self, *, require_idle: bool) -> None:
        current = self._current
        if current is None:
            return
        if require_idle and (current.active_prompt or current.pending_approvals):
            raise ConsoleError("AGENT_SESSION_BUSY", "Agent 运行期间不能切换会话", status_code=409)
        self._current = None
        lease = self._worker_lease
        self._worker_lease = None
        try:
            current.close()
        finally:
            if lease is not None:
                lease.release()

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


def _session_title(text: str) -> str:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "新会话")
    safe = str(redact(first_line))
    return safe if len(safe) <= 48 else safe[:47].rstrip() + "…"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
