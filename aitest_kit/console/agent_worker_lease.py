"""Cross-process workspace lease for the single active Pi Worker."""
from __future__ import annotations

import os
from pathlib import Path

from aitest_kit.console.errors import ConsoleError


class AgentWorkerLease:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._descriptor: int | None = None

    def acquire(self) -> None:
        if self._descriptor is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            os.ftruncate(descriptor, 1)
            _lock(descriptor)
        except OSError as exc:
            os.close(descriptor)
            raise ConsoleError(
                "AGENT_WORKER_ALREADY_ACTIVE",
                "当前 workspace 已有另一个 Console Pi Worker，请先关闭后再继续",
                status_code=409,
            ) from exc
        self._descriptor = descriptor
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def release(self) -> None:
        descriptor = self._descriptor
        if descriptor is None:
            return
        self._descriptor = None
        try:
            _unlock(descriptor)
        finally:
            os.close(descriptor)


if os.name == "nt":
    import msvcrt

    def _lock(descriptor: int) -> None:
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)

    def _unlock(descriptor: int) -> None:
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock(descriptor: int) -> None:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(descriptor: int) -> None:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
