"""File-backed metadata for local Pi Agent sessions."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aitest_kit.console.agent_worker_lease import AgentWorkerLease
from aitest_kit.console.errors import ConsoleError


SCHEMA_VERSION = 1
SESSION_HOME_ENV = "AITEST_AGENT_SESSION_HOME"
_LOGGER = logging.getLogger(__name__)
_PERMISSION_MODES = {"approval", "full_trust"}
_SESSION_STATUSES = {"created", "idle", "running", "awaiting_approval", "succeeded", "failed", "aborted", "interrupted"}


@dataclass
class AgentSessionRecord:
    schema_version: int
    session_id: str
    workspace_path: str
    permission_mode: str
    title: str
    status: str
    active_prompt: bool
    pending_approval_ids: list[str]
    last_seq: int
    created_at: str
    updated_at: str
    pi_session_id: str = ""
    pi_session_file: str = ""
    archived: bool = False

    def snapshot(self, *, is_active: bool) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "pi_session_id": self.pi_session_id,
            "permission_mode": self.permission_mode,
            "title": self.title,
            "status": self.status,
            "active_prompt": self.active_prompt,
            "pending_approval_ids": list(self.pending_approval_ids),
            "last_seq": self.last_seq,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_active": is_active,
        }


class AgentSessionStore:
    def __init__(self, root: str | Path | None = None) -> None:
        configured = root or os.environ.get(SESSION_HOME_ENV) or (Path.home() / ".aitest" / "sessions")
        self.root = Path(configured).expanduser().resolve(strict=False)

    def create(self, workspace: Path, permission_mode: str) -> AgentSessionRecord:
        workspace = workspace.resolve()
        now = _now()
        record = AgentSessionRecord(
            schema_version=SCHEMA_VERSION,
            session_id=str(uuid.uuid4()),
            workspace_path=str(workspace),
            permission_mode=permission_mode,
            title="新会话",
            status="created",
            active_prompt=False,
            pending_approval_ids=[],
            last_seq=0,
            created_at=now,
            updated_at=now,
        )
        directory = self.session_dir(workspace, record.session_id)
        self._ensure_private_directory(directory)
        (directory / "pi").mkdir(mode=0o700)
        _chmod_private(directory / "pi")
        self.save(record)
        return record

    def save(self, record: AgentSessionRecord) -> None:
        workspace = Path(record.workspace_path).resolve(strict=False)
        directory = self.session_dir(workspace, record.session_id)
        self._ensure_private_directory(directory)
        target = directory / "meta.json"
        temporary = directory / f".meta-{uuid.uuid4().hex}.tmp"
        payload = json.dumps(asdict(record), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            _chmod_private(target)
        finally:
            temporary.unlink(missing_ok=True)

    def load(
        self,
        workspace: Path,
        session_id: str,
        *,
        include_archived: bool = False,
    ) -> AgentSessionRecord:
        _validate_session_id(session_id)
        workspace = workspace.resolve()
        path = self.session_dir(workspace, session_id) / "meta.json"
        if not path.is_file():
            raise ConsoleError("AGENT_SESSION_NOT_FOUND", "Agent session 不存在", status_code=404)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            record = _record_from_json(raw)
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ConsoleError("AGENT_SESSION_METADATA_INVALID", "Agent session 元数据损坏", status_code=500) from exc
        if Path(record.workspace_path).resolve(strict=False) != workspace:
            raise ConsoleError("AGENT_SESSION_NOT_FOUND", "Agent session 不属于当前 workspace", status_code=404)
        if record.archived and not include_archived:
            raise ConsoleError("AGENT_SESSION_NOT_FOUND", "Agent session 不存在", status_code=404)
        return record

    def list(self, workspace: Path, *, include_archived: bool = False) -> list[AgentSessionRecord]:
        workspace = workspace.resolve()
        root = self.workspace_dir(workspace)
        if not root.is_dir():
            return []
        records: list[AgentSessionRecord] = []
        for directory in root.iterdir():
            if not directory.is_dir():
                continue
            try:
                record = self.load(workspace, directory.name, include_archived=True)
            except ConsoleError as exc:
                _LOGGER.warning("Ignoring invalid Agent session metadata under %s: %s", directory, exc)
                continue
            if include_archived or not record.archived:
                records.append(record)
        return sorted(records, key=lambda item: (item.updated_at, item.created_at), reverse=True)

    def archive(self, workspace: Path, session_id: str) -> AgentSessionRecord:
        record = self.load(workspace, session_id)
        record.archived = True
        record.active_prompt = False
        record.pending_approval_ids = []
        record.updated_at = _now()
        self.save(record)
        return record

    def remove_new(self, workspace: Path, session_id: str) -> None:
        _validate_session_id(session_id)
        directory = self.session_dir(workspace.resolve(), session_id)
        if directory.parent == self.workspace_dir(workspace.resolve()) and directory.exists():
            shutil.rmtree(directory)

    def workspace_dir(self, workspace: Path) -> Path:
        canonical = str(workspace.resolve()).encode("utf-8")
        return self.root / hashlib.sha256(canonical).hexdigest()[:24]

    def session_dir(self, workspace: Path, session_id: str) -> Path:
        _validate_session_id(session_id)
        return self.workspace_dir(workspace) / session_id

    def event_path(self, workspace: Path, session_id: str) -> Path:
        return self.session_dir(workspace.resolve(), session_id) / "events.jsonl"

    def worker_lease(self, workspace: Path) -> AgentWorkerLease:
        directory = self.workspace_dir(workspace.resolve())
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        _chmod_private(self.root)
        _chmod_private(directory)
        return AgentWorkerLease(directory / ".worker.lock")

    def pi_dir(self, workspace: Path, session_id: str) -> Path:
        directory = self.session_dir(workspace.resolve(), session_id) / "pi"
        self._ensure_private_directory(directory.parent)
        directory.mkdir(exist_ok=True, mode=0o700)
        _chmod_private(directory)
        return directory.resolve()

    def _ensure_private_directory(self, directory: Path) -> None:
        workspace_directory = directory if directory.parent == self.root else directory.parent
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        workspace_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        for path in (self.root, workspace_directory, directory):
            _chmod_private(path)

    def set_pi_session_file(self, record: AgentSessionRecord, raw_path: str) -> None:
        if not raw_path:
            return
        directory = self.session_dir(Path(record.workspace_path), record.session_id).resolve()
        pi_directory = (directory / "pi").resolve()
        path = Path(raw_path).resolve(strict=False)
        try:
            path.relative_to(pi_directory)
            relative = path.relative_to(directory)
        except ValueError as exc:
            raise ConsoleError("AGENT_SESSION_PATH_INVALID", "Pi session 文件越出 AITest Pi session 目录", status_code=502) from exc
        record.pi_session_file = relative.as_posix()

    def resolve_pi_session_file(self, record: AgentSessionRecord) -> Path | None:
        if not record.pi_session_file:
            return None
        directory = self.session_dir(Path(record.workspace_path), record.session_id).resolve()
        pi_directory = (directory / "pi").resolve()
        path = (directory / record.pi_session_file).resolve(strict=False)
        try:
            path.relative_to(pi_directory)
        except ValueError as exc:
            raise ConsoleError("AGENT_SESSION_PATH_INVALID", "Pi session 文件越出 AITest Pi session 目录", status_code=500) from exc
        return path


def _record_from_json(raw: Any) -> AgentSessionRecord:
    if not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported Agent session metadata")
    required_strings = (
        "session_id",
        "workspace_path",
        "permission_mode",
        "title",
        "status",
        "created_at",
        "updated_at",
    )
    if any(not isinstance(raw.get(key), str) for key in required_strings):
        raise ValueError("Agent session metadata is incomplete")
    _validate_session_id(raw["session_id"])
    if raw["permission_mode"] not in _PERMISSION_MODES:
        raise ValueError("permission mode is invalid")
    if raw["status"] not in _SESSION_STATUSES:
        raise ValueError("session status is invalid")
    pending = raw.get("pending_approval_ids", [])
    if not isinstance(pending, list) or not all(isinstance(item, str) for item in pending):
        raise ValueError("pending approval ids are invalid")
    return AgentSessionRecord(
        schema_version=SCHEMA_VERSION,
        session_id=raw["session_id"],
        workspace_path=raw["workspace_path"],
        permission_mode=raw["permission_mode"],
        title=raw["title"],
        status=raw["status"],
        active_prompt=bool(raw.get("active_prompt", False)),
        pending_approval_ids=list(pending),
        last_seq=int(raw.get("last_seq", 0)),
        created_at=raw["created_at"],
        updated_at=raw["updated_at"],
        pi_session_id=str(raw.get("pi_session_id", "")),
        pi_session_file=str(raw.get("pi_session_file", "")),
        archived=bool(raw.get("archived", False)),
    )


def _validate_session_id(session_id: str) -> None:
    try:
        parsed = uuid.UUID(session_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ConsoleError("AGENT_SESSION_NOT_FOUND", "Agent session 不存在", status_code=404) from exc
    if str(parsed) != session_id:
        raise ConsoleError("AGENT_SESSION_NOT_FOUND", "Agent session 不存在", status_code=404)


def _chmod_private(path: Path) -> None:
    try:
        path.chmod(0o700 if path.is_dir() else 0o600)
    except OSError:
        pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
