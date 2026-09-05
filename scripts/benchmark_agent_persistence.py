#!/usr/bin/env python3
"""Measure real journal + metadata durability, not model/SSE/browser performance."""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aitest_kit.console.agent_event_log import AgentEventLog
from aitest_kit.console.agent_session_store import AgentSessionStore


def measure(root: Path, *, count: int, payload_bytes: int) -> dict:
    if count < 1 or payload_bytes < 1:
        raise ValueError("Event count and payload bytes must be positive")
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    store = AgentSessionStore(root / "sessions")
    record = store.create(workspace, "approval")
    journal_path = store.event_path(workspace, record.session_id)
    events = AgentEventLog(journal_path=journal_path)
    fsync = os.fsync
    sync_durations = []
    latencies = []

    def timed_sync(descriptor):
        started = time.perf_counter()
        fsync(descriptor)
        sync_durations.append(time.perf_counter() - started)

    payload = {"delta": "x" * payload_bytes}
    started = time.perf_counter()
    with patch("os.fsync", timed_sync):
        for _ in range(count):
            before = time.perf_counter()
            events.append(record.session_id, "text_delta", payload)
            record.last_seq = events.last_seq
            record.updated_at = datetime.now(timezone.utc).isoformat()
            store.save(record)
            latencies.append((time.perf_counter() - before) * 1000)
    elapsed = time.perf_counter() - started
    events.close()
    before = time.perf_counter()
    reopened = AgentEventLog(journal_path=journal_path)
    metadata = store.load(workspace, record.session_id)
    reopen_ms = (time.perf_counter() - before) * 1000
    reopened.close()
    ordered = sorted(latencies)
    return {
        "events": count, "payload_bytes": payload_bytes,
        "elapsed_seconds": elapsed, "events_per_second": count / elapsed,
        "latency_ms": {"p50": ordered[math.ceil(count * .50) - 1],
                       "p95": ordered[math.ceil(count * .95) - 1], "max": ordered[-1]},
        "fsync_calls": len(sync_durations), "fsync_seconds": sum(sync_durations),
        "journal_bytes": journal_path.stat().st_size,
        "metadata_bytes": (journal_path.parent / "meta.json").stat().st_size,
        "reopen_ms": reopen_ms, "reopened_seq": reopened.last_seq, "metadata_seq": metadata.last_seq,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, default=1000)
    parser.add_argument("--payload-bytes", type=int, default=128)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if min(args.events, args.payload_bytes, args.repeats) < 1:
        parser.error("events, payload-bytes and repeats must be positive")
    with tempfile.TemporaryDirectory(prefix="aitest persistence benchmark ") as temporary:
        rows = [measure(Path(temporary) / str(index), count=args.events, payload_bytes=args.payload_bytes)
                for index in range(args.repeats)]
    report = {"measured_at": datetime.now(timezone.utc).isoformat(), "os": platform.platform(),
              "machine": platform.machine(), "python": platform.python_version(),
              "scope": "journal append + metadata save; real fsync; no model/SSE/browser", "runs": rows}
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
