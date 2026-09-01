"""Authenticated Console boundary for the user-level Pi Runtime."""
from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel

from aitest_kit.agent.runtime import runtime_home, runtime_setup_command, runtime_status
from aitest_kit.console.errors import ConsoleError
from aitest_kit.console.jobs import JobManager


class RuntimeSetupRequest(BaseModel):
    confirmed: bool = False


class AgentRuntimeService:
    def __init__(self, session_snapshot: Callable[[], dict[str, Any] | None]) -> None:
        self._session_snapshot = session_snapshot
        self._root = runtime_home()
        self._jobs = JobManager(self._root)

    def status(self) -> dict[str, Any]:
        return runtime_status()

    def start_setup(self, *, confirmed: bool) -> dict[str, Any]:
        if not confirmed:
            raise ConsoleError(
                "AGENT_RUNTIME_SETUP_CONFIRMATION_REQUIRED",
                "安装会访问 npm registry 并写入用户级 Runtime 目录，需要明确确认",
                status_code=403,
            )
        if self._session_snapshot() is not None:
            raise ConsoleError("AGENT_SESSION_ACTIVE", "请先关闭当前 Agent session", status_code=409)
        self._root.mkdir(parents=True, exist_ok=True)
        try:
            job = self._jobs.start_argv(
                operation="agent_runtime_setup",
                command=runtime_setup_command(),
                command_summary="aitest agent setup",
                env=dict(os.environ),
            )
        except RuntimeError as exc:
            raise ConsoleError("JOB_ALREADY_RUNNING", "Agent Runtime 安装任务正在运行", status_code=409) from exc
        return job.public()

    def get_setup(self, job_id: str) -> dict[str, Any]:
        try:
            return self._jobs.get(job_id).public()
        except KeyError as exc:
            raise ConsoleError(
                "AGENT_RUNTIME_SETUP_JOB_NOT_FOUND",
                "Agent Runtime 安装任务不存在",
                status_code=404,
            ) from exc

    def cancel_setup(self, job_id: str) -> dict[str, Any]:
        try:
            self._jobs.cancel(job_id)
            return self._jobs.get(job_id).public()
        except KeyError as exc:
            raise ConsoleError(
                "AGENT_RUNTIME_SETUP_JOB_NOT_FOUND",
                "Agent Runtime 安装任务不存在",
                status_code=404,
            ) from exc

    def close(self) -> None:
        for job in self._jobs.list():
            if job["status"] in {"queued", "running"}:
                self._jobs.cancel(job["id"])


def create_agent_runtime_router(service: AgentRuntimeService) -> APIRouter:
    router = APIRouter(prefix="/api/agent/runtime")

    @router.get("")
    def get_runtime(response: Response) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return service.status()

    @router.post("/setup")
    async def start_setup(payload: RuntimeSetupRequest, response: Response) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return service.start_setup(confirmed=payload.confirmed)

    @router.get("/setup/{job_id}")
    async def get_setup(job_id: str, response: Response) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return service.get_setup(job_id)

    @router.post("/setup/{job_id}/cancel")
    async def cancel_setup(job_id: str, response: Response) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return service.cancel_setup(job_id)

    return router
