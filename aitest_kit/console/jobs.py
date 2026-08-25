from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from aitest_kit.registry import load_module_context, load_target_context
from aitest_kit.workspace_config import AITEST_CONFIG_PATH, load_workspace_paths


_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
_CASE_ID = re.compile(r"^TC-[A-Z0-9]+-\d+$")
_IS_WINDOWS = os.name == "nt"


@dataclass(frozen=True)
class Selector:
    type: str
    suite_file: str = ""
    task_file: str = ""
    target: str = ""
    module: str = ""
    case_ids: list[str] = field(default_factory=list)


@dataclass
class Job:
    id: str
    operation: str
    command_summary: str
    status: str = "queued"
    output: str = ""
    exit_code: int | None = None
    started_at: str = ""
    finished_at: str = ""
    cancel_requested: bool = False
    process: subprocess.Popen[str] | None = field(default=None, repr=False)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "operation": self.operation,
            "command_summary": self.command_summary,
            "status": self.status,
            "output": self.output,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "cancel_requested": self.cancel_requested,
        }


def build_aitest_command(*, root: Path, operation: str, selector: Selector) -> list[str]:
    root = root.expanduser().resolve()
    command_name = "run" if operation == "run" else "codegen"
    if operation not in {"validate_profile", "codegen", "freshness", "run"}:
        raise ValueError("unsupported operation")
    command = [sys.executable, "-m", "aitest_kit.cli", command_name]
    command.extend(_selector_args(root, selector, operation=operation))
    if operation == "validate_profile":
        command.append("--validate-profile")
    elif operation == "freshness":
        command.append("--check")
    return command


def _selector_args(root: Path, selector: Selector, *, operation: str) -> list[str]:
    if selector.type in {"suite", "case"}:
        manifest = _manifest_inside(root, selector.suite_file, "suite.yaml")
        args = ["--suite-file", str(manifest)]
        if selector.type == "case":
            if operation != "run":
                raise ValueError("case selector is only supported for run")
            if not selector.case_ids or any(not _CASE_ID.fullmatch(item) for item in selector.case_ids):
                raise ValueError("invalid case selector")
            for case_id in selector.case_ids:
                args.extend(["--case-id", case_id])
        return args
    if selector.type == "task":
        return ["--task-file", str(_manifest_inside(root, selector.task_file, ".yaml"))]
    if selector.type == "module":
        _valid_name(selector.target)
        _valid_name(selector.module)
        target_path = _profile_dir(root) / selector.target / "target.yaml"
        if not target_path.exists():
            raise ValueError("target selector not found in workspace")
        target_context = load_target_context(target_path, workspace_root=root)
        module_context = load_module_context(target_context, selector.module)
        if module_context.config_path is None or not module_context.config_path.exists():
            raise ValueError("module selector not found in workspace")
        return ["--target", selector.target, "--module", selector.module]
    if selector.type == "target":
        _valid_name(selector.target)
        target_path = _profile_dir(root) / selector.target / "target.yaml"
        if not target_path.exists():
            raise ValueError("target selector not found in workspace")
        return ["--target", selector.target]
    raise ValueError("invalid selector type")


def _manifest_inside(root: Path, raw_path: str, expected_name: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = root / path
    path = path.resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("manifest path must stay inside workspace") from exc
    if not path.exists() or not path.is_file():
        raise ValueError("manifest not found in workspace")
    if expected_name == "suite.yaml" and path.name != expected_name:
        raise ValueError("suite selector requires suite.yaml")
    if expected_name == ".yaml" and path.suffix not in {".yaml", ".yml"}:
        raise ValueError("task selector requires yaml")
    return path


def _valid_name(value: str) -> None:
    if not value or not _NAME.fullmatch(value):
        raise ValueError("invalid registry name")


def _profile_dir(root: Path) -> Path:
    configured = load_workspace_paths(root / AITEST_CONFIG_PATH).profile_dir
    path = configured if configured.is_absolute() else root / configured
    resolved = path.expanduser().resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("configured profile directory must stay inside workspace") from exc
    return resolved


class JobManager:
    def __init__(
        self,
        root: Path,
        *,
        max_output_chars: int = 120_000,
        cancel_timeout: float = 2.0,
    ) -> None:
        self.root = root.expanduser().resolve()
        self.max_output_chars = max_output_chars
        self.cancel_timeout = cancel_timeout
        self._lock = threading.RLock()
        self._jobs: dict[str, Job] = {}

    def start_argv(
        self,
        *,
        operation: str,
        command: list[str],
        command_summary: str,
        env: dict[str, str] | None = None,
        redaction_values: list[str] | None = None,
    ) -> Job:
        with self._lock:
            active = next((job for job in self._jobs.values() if job.status in {"queued", "running"}), None)
            if active is not None:
                raise RuntimeError("a job is already running")
            job = Job(id=uuid4().hex, operation=operation, command_summary=command_summary)
            self._jobs[job.id] = job
        thread = threading.Thread(
            target=self._run,
            args=(job.id, list(command), dict(env or os.environ), list(redaction_values or [])),
            daemon=True,
        )
        thread.start()
        return job

    def get(self, job_id: str) -> Job:
        with self._lock:
            try:
                return self._jobs[job_id]
            except KeyError as exc:
                raise KeyError("job not found") from exc

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda item: item.started_at or item.id, reverse=True)
            return [job.public() for job in jobs]

    def cancel(self, job_id: str) -> None:
        with self._lock:
            job = self.get(job_id)
            if job.status not in {"queued", "running"}:
                return
            job.cancel_requested = True
            process = job.process
        if process is not None and process.poll() is None:
            _terminate_process_group(process)
            thread = threading.Thread(
                target=_escalate_cancel,
                args=(process, self.cancel_timeout),
                daemon=True,
            )
            thread.start()

    def _run(self, job_id: str, command: list[str], env: dict[str, str], redactions: list[str]) -> None:
        job = self.get(job_id)
        with self._lock:
            job.status = "running"
            job.started_at = _now()
        try:
            process = subprocess.Popen(
                command,
                cwd=self.root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                **_popen_group_options(),
            )
            with self._lock:
                job.process = process
                cancel_now = job.cancel_requested
            if cancel_now:
                _terminate_process_group(process)
            assert process.stdout is not None
            for line in process.stdout:
                self._append(job, _redact(line, redactions))
            try:
                exit_code = process.wait(timeout=self.cancel_timeout)
            except subprocess.TimeoutExpired:
                _kill_process_group(process)
                exit_code = process.wait(timeout=self.cancel_timeout)
            with self._lock:
                job.exit_code = exit_code
                job.status = "cancelled" if job.cancel_requested else "succeeded" if exit_code == 0 else "failed"
        except OSError as exc:
            self._append(job, f"Unable to start process: {type(exc).__name__}\n")
            with self._lock:
                job.exit_code = -1
                job.status = "cancelled" if job.cancel_requested else "failed"
        finally:
            with self._lock:
                job.finished_at = _now()
                job.process = None

    def _append(self, job: Job, text: str) -> None:
        with self._lock:
            job.output += text
            if len(job.output) > self.max_output_chars:
                job.output = "[earlier output truncated]\n" + job.output[-self.max_output_chars :]


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    if _IS_WINDOWS:
        ctrl_break = getattr(signal, "CTRL_BREAK_EVENT", None)
        if ctrl_break is not None:
            try:
                process.send_signal(ctrl_break)
                return
            except (OSError, ValueError):
                pass
        process.terminate()
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        process.terminate()


def _kill_process_group(process: subprocess.Popen[str]) -> None:
    if _IS_WINDOWS:
        process.kill()
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        process.kill()


def _popen_group_options() -> dict[str, Any]:
    if _IS_WINDOWS:
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}


def _escalate_cancel(process: subprocess.Popen[str], timeout: float) -> None:
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process_group(process)


def _redact(text: str, values: list[str]) -> str:
    result = text
    for value in values:
        if value:
            result = result.replace(value, "[REDACTED]")
    return result


def _now() -> str:
    return datetime.now().astimezone().isoformat()
