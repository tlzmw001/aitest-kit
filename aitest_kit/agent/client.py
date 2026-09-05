"""Long-lived JSONL client for the local Pi Worker process."""
from __future__ import annotations

import os
import queue
import signal
import subprocess
import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from aitest_kit.agent.protocol import ProtocolError, ProtocolMessage, redact


ApprovalHandler = Callable[[ProtocolMessage], str]
EventHandler = Callable[[ProtocolMessage], None]
_EOF = object()


class AgentWorkerError(RuntimeError):
    """Stable worker/control-plane failure."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = dict(redact(details or {}))


class WorkerClient:
    """Own one Worker subprocess and enforce handshake, timeout, and cleanup rules."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        startup_timeout: float = 15,
        message_timeout: float = 300,
        shutdown_timeout: float = 5,
    ) -> None:
        self.command = [str(part) for part in command]
        self.env = dict(env) if env is not None else None
        self.startup_timeout = startup_timeout
        self.message_timeout = message_timeout
        self.shutdown_timeout = shutdown_timeout
        self._process: subprocess.Popen[str] | None = None
        self._messages: queue.Queue[object] = queue.Queue()
        self._stderr_lines: list[str] = []
        self._secret_values = _environment_secret_values(self.env or {})
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._write_lock = threading.Lock()
        self._started = False
        self._closed = False

    @property
    def returncode(self) -> int | None:
        return self._process.returncode if self._process is not None else None

    def start(self, initialize_payload: Mapping[str, Any]) -> ProtocolMessage:
        if self._process is not None:
            raise AgentWorkerError("WORKER_ALREADY_STARTED", "worker has already been started")
        popen_options: dict[str, Any] = {}
        if os.name == "nt":
            popen_options["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            popen_options["start_new_session"] = True
        try:
            self._process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
                env=self.env,
                **popen_options,
            )
        except OSError as exc:
            raise AgentWorkerError("WORKER_START_FAILED", f"无法启动 Pi Worker: {exc}") from exc
        self._stdout_thread = threading.Thread(
            target=self._read_stdout,
            name="aitest-agent-stdout",
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._read_stderr,
            name="aitest-agent-stderr",
            daemon=True,
        )
        try:
            self._stdout_thread.start()
            self._stderr_thread.start()
            message_id = self.send("initialize", initialize_payload)
            event = self.read_event(timeout=self.startup_timeout)
            if event.id != message_id or event.type != "ready":
                raise AgentWorkerError(
                    "WORKER_HANDSHAKE_FAILED",
                    f"Pi Worker 握手失败，收到 {event.type}",
                )
        except BaseException:
            self._terminate()
            raise
        self._started = True
        return event

    def send(self, message_type: str, payload: Mapping[str, Any] | None = None) -> str:
        process = self._require_process()
        if process.poll() is not None or process.stdin is None:
            raise self._exited_error()
        message = ProtocolMessage.create(message_type, payload)
        try:
            with self._write_lock:
                process.stdin.write(message.to_line() + "\n")
                process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise self._exited_error() from exc
        return message.id

    def send_prompt(self, text: str) -> str:
        """Send a prompt without consuming its event stream."""
        return self.send("prompt", {"text": text})

    def send_permission_decision(self, request_id: str, decision: str) -> str:
        """Resolve one permission request without consuming worker events."""
        return self.send(
            "permission_decision",
            {"request_id": request_id, "decision": decision},
        )

    def request_abort(self) -> str:
        """Request abort while leaving acknowledgement consumption to the caller."""
        return self.send("abort")

    def request_shutdown(self) -> str:
        """Request shutdown while leaving acknowledgement consumption to the caller."""
        return self.send("shutdown")

    def wait_for_exit(self, *, timeout: float | None = None) -> None:
        """Wait for a previously requested shutdown and terminate on timeout."""
        process = self._process
        if process is None:
            return
        try:
            process.wait(timeout=self.shutdown_timeout if timeout is None else timeout)
        except subprocess.TimeoutExpired:
            self._terminate()
        self._closed = True

    def read_event(self, *, timeout: float | None = None) -> ProtocolMessage:
        wait = self.message_timeout if timeout is None else timeout
        try:
            item = self._messages.get(timeout=wait)
        except queue.Empty as exc:
            raise AgentWorkerError("WORKER_TIMEOUT", f"等待 Pi Worker 消息超时（{wait:g}s）") from exc
        if item is _EOF:
            raise self._exited_error()
        if isinstance(item, Exception):
            if isinstance(item, ProtocolError):
                raise AgentWorkerError(item.code, str(item)) from item
            raise AgentWorkerError("WORKER_READ_FAILED", str(item)) from item
        if not isinstance(item, ProtocolMessage):
            raise AgentWorkerError("WORKER_READ_FAILED", "worker reader returned an invalid item")
        return item

    def run_prompt(
        self,
        text: str,
        *,
        on_event: EventHandler | None = None,
        approval_handler: ApprovalHandler | None = None,
        timeout: float | None = None,
    ) -> list[ProtocolMessage]:
        self.send("prompt", {"text": text})
        events: list[ProtocolMessage] = []
        while True:
            event = self.read_event(timeout=timeout)
            events.append(event)
            if on_event:
                on_event(event)
            if event.type == "permission_requested":
                decision = "deny"
                if approval_handler is not None:
                    try:
                        decision = approval_handler(event)
                    except Exception:  # noqa: BLE001 - an unavailable UI must fail closed.
                        decision = "deny"
                if decision not in {"allow_once", "allow_session", "deny"}:
                    decision = "deny"
                self.send(
                    "permission_decision",
                    {"request_id": event.payload.get("request_id", event.id), "decision": decision},
                )
            elif event.type == "error":
                raise AgentWorkerError(
                    str(event.payload.get("code", "WORKER_ERROR")),
                    str(event.payload.get("message", "Pi Worker failed")),
                    details=event.payload.get("details") if isinstance(event.payload.get("details"), dict) else None,
                )
            elif event.type == "agent_finished":
                return events

    def abort(self) -> ProtocolMessage:
        message_id = self.send("abort")
        while True:
            event = self.read_event(timeout=self.shutdown_timeout)
            if event.id == message_id and event.type == "aborted":
                return event
            if event.type == "error":
                raise AgentWorkerError(
                    str(event.payload.get("code", "ABORT_FAILED")),
                    str(event.payload.get("message", "Pi Worker abort failed")),
                )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        process = self._process
        if process is None:
            return
        if process.poll() is None:
            try:
                message_id = self.send("shutdown")
                while True:
                    event = self.read_event(timeout=self.shutdown_timeout)
                    if event.id == message_id and event.type == "shutdown_complete":
                        break
            except AgentWorkerError:
                pass
        try:
            process.wait(timeout=self.shutdown_timeout)
        except subprocess.TimeoutExpired:
            self._terminate()

    def __enter__(self) -> "WorkerClient":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def _read_stdout(self) -> None:
        process = self._require_process()
        assert process.stdout is not None
        try:
            for line in process.stdout:
                stripped = line.rstrip("\r\n")
                if not stripped:
                    continue
                self._messages.put(ProtocolMessage.from_line(stripped))
        except Exception as exc:  # noqa: BLE001 - transfer the reader failure to the caller.
            self._messages.put(exc)
        finally:
            self._messages.put(_EOF)

    def _read_stderr(self) -> None:
        process = self._require_process()
        assert process.stderr is not None
        for line in process.stderr:
            safe = str(redact(line.rstrip()))
            for secret in self._secret_values:
                safe = safe.replace(secret, "[REDACTED]")
            self._stderr_lines.append(safe)
            if len(self._stderr_lines) > 100:
                del self._stderr_lines[0]

    def _require_process(self) -> subprocess.Popen[str]:
        if self._process is None:
            raise AgentWorkerError("WORKER_NOT_STARTED", "worker has not been started")
        return self._process

    def _exited_error(self) -> AgentWorkerError:
        process = self._require_process()
        returncode = process.poll()
        if returncode is None:
            try:
                returncode = process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                returncode = None
        if self._stderr_thread is not None and self._stderr_thread is not threading.current_thread():
            self._stderr_thread.join(timeout=0.2)
        suffix = f"，退出码 {returncode}" if returncode is not None else ""
        details = {"stderr": self._stderr_lines[-10:]} if self._stderr_lines else None
        return AgentWorkerError("WORKER_EXITED", f"Pi Worker 已退出{suffix}", details=details)

    def _terminate(self) -> None:
        process = self._require_process()
        if process.poll() is not None:
            return
        try:
            if os.name == "nt":
                process.send_signal(getattr(signal, "CTRL_BREAK_EVENT", signal.SIGTERM))
            else:
                os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=self.shutdown_timeout)
            return
        except (OSError, subprocess.TimeoutExpired):
            pass
        if process.poll() is None:
            try:
                if os.name == "nt":
                    process.kill()
                else:
                    os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                process.kill()
            try:
                process.wait(timeout=self.shutdown_timeout)
            except subprocess.TimeoutExpired:
                pass


def default_worker_dir() -> Path:
    from aitest_kit.agent.runtime import AgentRuntimeError, resolve_worker_dir

    try:
        return resolve_worker_dir()
    except AgentRuntimeError as exc:
        raise AgentWorkerError(exc.code, str(exc), details=exc.details) from exc


def default_worker_command(worker_dir: str | Path | None = None) -> list[str]:
    root = Path(worker_dir) if worker_dir is not None else default_worker_dir()
    return ["node", "--experimental-strip-types", str(root / "src" / "worker.ts")]


def _environment_secret_values(environ: Mapping[str, str]) -> tuple[str, ...]:
    sensitive_fragments = ("KEY", "PASSWORD", "SECRET", "TOKEN")
    return tuple(
        value
        for name, value in environ.items()
        if value and len(value) >= 4 and any(fragment in name.upper() for fragment in sensitive_fragments)
    )
