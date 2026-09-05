"""Recovery writes share the active Worker's workspace lease."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from aitest_kit.console.agent_event_log import AgentEventLog
from aitest_kit.console.agent_session_store import AgentSessionRecord, AgentSessionStore
from aitest_kit.console.agent_worker_lease import AgentWorkerLease
from aitest_kit.console.errors import ConsoleError


@contextmanager
def session_write_lease(store: AgentSessionStore, workspace: Path, held: AgentWorkerLease | None):
    lease = held or store.worker_lease(workspace)
    lease.acquire()
    try:
        yield lease
    finally:
        if held is None:
            lease.release()


def recover_session(
    store: AgentSessionStore,
    record: AgentSessionRecord,
    held: AgentWorkerLease | None = None,
) -> AgentSessionRecord:
    if not (record.active_prompt or record.pending_approval_ids or record.status in {"running", "awaiting_approval"}):
        return record
    workspace = Path(record.workspace_path)
    try:
        with session_write_lease(store, workspace, held):
            # A worker may have completed between the initial read and acquisition.
            record = store.load(workspace, record.session_id)
            if not (record.active_prompt or record.pending_approval_ids or record.status in {"running", "awaiting_approval"}):
                return record
            events = AgentEventLog(journal_path=store.event_path(workspace, record.session_id))
            events.append(record.session_id, "session_interrupted", {
                "reason": "runtime_restart", "tool_result_unknown": True,
            })
            record.status = "interrupted"
            record.active_prompt = False
            record.pending_approval_ids = []
            record.last_seq = events.last_seq
            record.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            store.save(record)
            return record
    except ConsoleError as exc:
        if exc.code != "AGENT_WORKER_ALREADY_ACTIVE":
            raise
        # History remains readable, but a live owner's state must never be recovered.
        return record
