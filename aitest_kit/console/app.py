from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from aitest_kit.console.errors import ConsoleError
from aitest_kit.console.files import (
    env_secret_values,
    environment_metadata,
    read_workspace_file,
    reveal_env,
    save_env,
    save_workspace_file,
)
from aitest_kit.console.jobs import JobManager, Selector, build_aitest_command
from aitest_kit.console.workspace import WorkspaceState


class OpenWorkspaceRequest(BaseModel):
    path: str


class InitializeWorkspaceRequest(OpenWorkspaceRequest):
    confirmed: bool = False


class SaveFileRequest(BaseModel):
    path: str
    content: str
    sha256: str


class SensitivePathRequest(BaseModel):
    path: str
    confirmed: bool = False


class SaveEnvRequest(SaveFileRequest):
    confirmed: bool = False


class SelectorRequest(BaseModel):
    type: str
    suite_file: str = ""
    task_file: str = ""
    target: str = ""
    module: str = ""
    case_ids: list[str] = Field(default_factory=list)


class StartJobRequest(BaseModel):
    operation: str
    selector: SelectorRequest
    env_file: Optional[str] = None


class ConsoleRuntime:
    def __init__(self, initial_workspace: str | Path | None) -> None:
        self.workspace = WorkspaceState(initial_workspace)
        self.jobs = JobManager(self.workspace.root) if initial_workspace is not None else None

    def open_workspace(self, path: str) -> dict[str, Any]:
        self._ensure_workspace_switch_allowed()
        root = self.workspace.open(path)
        self.jobs = JobManager(root)
        return self.workspace.snapshot()

    def initialize_workspace(self, path: str, *, confirmed: bool) -> dict[str, Any]:
        if not confirmed:
            raise ConsoleError(
                "WORKSPACE_INIT_CONFIRMATION_REQUIRED",
                "初始化会向所选目录写入 AITest workspace 文件，需要用户明确确认",
                status_code=403,
            )
        self._ensure_workspace_switch_allowed()
        root = self.workspace.initialize(path)
        self.jobs = JobManager(root)
        return self.workspace.snapshot()

    def _ensure_workspace_switch_allowed(self) -> None:
        if self.jobs is not None and any(job["status"] in {"queued", "running"} for job in self.jobs.list()):
            raise ConsoleError("JOB_ALREADY_RUNNING", "任务运行期间不能切换 workspace", status_code=409)

    def require_jobs(self) -> JobManager:
        self.workspace.root
        if self.jobs is None:
            self.jobs = JobManager(self.workspace.root)
        return self.jobs


def create_app(
    *,
    initial_workspace: str | Path | None = None,
    token: str,
    static_dir: str | Path | None = None,
) -> FastAPI:
    app = FastAPI(title="AITest Local Console", docs_url=None, redoc_url=None)
    runtime = ConsoleRuntime(initial_workspace)
    app.state.console_runtime = runtime
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$",
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Content-Type", "X-AITest-Console-Token"],
    )

    @app.exception_handler(ConsoleError)
    async def console_error_handler(_request: Request, exc: ConsoleError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    async def require_token(request: Request) -> None:
        provided = request.headers.get("X-AITest-Console-Token")
        if not provided or not _constant_time_equal(provided, token):
            raise ConsoleError("UNAUTHORIZED", "Console session token 无效", status_code=401)

    auth = Depends(require_token)

    @app.get("/api/health", dependencies=[auth])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/workspace", dependencies=[auth])
    async def workspace() -> dict[str, Any]:
        return runtime.workspace.snapshot()

    @app.post("/api/workspace/open", dependencies=[auth])
    async def open_workspace(payload: OpenWorkspaceRequest) -> dict[str, Any]:
        return runtime.open_workspace(payload.path)

    @app.post("/api/workspace/initialize", dependencies=[auth])
    async def initialize_workspace(payload: InitializeWorkspaceRequest) -> dict[str, Any]:
        return runtime.initialize_workspace(payload.path, confirmed=payload.confirmed)

    @app.get("/api/files", dependencies=[auth])
    async def read_file(path: str) -> dict[str, Any]:
        return read_workspace_file(runtime.workspace, path)

    @app.put("/api/files", dependencies=[auth])
    async def write_file(payload: SaveFileRequest) -> dict[str, Any]:
        return save_workspace_file(
            runtime.workspace,
            raw_path=payload.path,
            content=payload.content,
            expected_sha256=payload.sha256,
        )

    @app.get("/api/environment", dependencies=[auth])
    async def environment(response: Response) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return environment_metadata(runtime.workspace)

    @app.post("/api/environment/grants", dependencies=[auth])
    async def grant_environment(payload: SensitivePathRequest) -> dict[str, Any]:
        if not payload.confirmed:
            raise ConsoleError("ENV_ACCESS_REQUIRED", "需要用户明确授权外部 env 文件", status_code=403)
        path = runtime.workspace.grant_external_env(payload.path)
        return {"path": str(path), "granted": True}

    @app.post("/api/environment/reveal", dependencies=[auth])
    async def reveal_environment(payload: SensitivePathRequest, response: Response) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return reveal_env(runtime.workspace, raw_path=payload.path, confirmed=payload.confirmed)

    @app.put("/api/environment/files", dependencies=[auth])
    async def write_environment(payload: SaveEnvRequest, response: Response) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return save_env(
            runtime.workspace,
            raw_path=payload.path,
            content=payload.content,
            expected_sha256=payload.sha256,
            confirmed=payload.confirmed,
        )

    @app.put("/api/environment/active", dependencies=[auth])
    async def set_active_environment(payload: SensitivePathRequest) -> dict[str, Any]:
        if not payload.confirmed:
            raise ConsoleError("ENV_ACCESS_REQUIRED", "需要用户确认运行 env 文件", status_code=403)
        path = runtime.workspace.set_active_env(payload.path)
        return {"path": str(path) if path else None}

    @app.get("/api/reports", dependencies=[auth])
    async def reports(limit: int = 100) -> dict[str, Any]:
        return {"reports": runtime.workspace.list_reports(limit=max(1, min(limit, 500)))}

    @app.get("/api/reports/detail", dependencies=[auth])
    async def report_detail(path: str) -> dict[str, Any]:
        return runtime.workspace.report_detail(path)

    @app.post("/api/jobs", dependencies=[auth])
    async def start_job(payload: StartJobRequest) -> dict[str, Any]:
        selector_data = (
            payload.selector.model_dump()
            if hasattr(payload.selector, "model_dump")
            else payload.selector.dict()
        )
        selector = Selector(**selector_data)
        try:
            command = build_aitest_command(
                root=runtime.workspace.root,
                operation=payload.operation,
                selector=selector,
            )
        except ValueError as exc:
            raise ConsoleError("SELECTOR_INVALID", str(exc)) from exc
        env = dict(os.environ)
        if payload.env_file:
            env_path = runtime.workspace.resolve_env(payload.env_file, allow_missing=False)
            env["AITEST_ENV_FILE"] = str(env_path)
        summary = _command_summary(runtime.workspace.root, command)
        try:
            job = runtime.require_jobs().start_argv(
                operation=payload.operation,
                command=command,
                command_summary=summary,
                env=env,
                redaction_values=env_secret_values(runtime.workspace, payload.env_file),
            )
        except RuntimeError as exc:
            raise ConsoleError("JOB_ALREADY_RUNNING", "当前 workspace 已有任务运行", status_code=409) from exc
        return job.public()

    @app.get("/api/jobs", dependencies=[auth])
    async def jobs() -> dict[str, Any]:
        return {"jobs": runtime.require_jobs().list()}

    @app.get("/api/jobs/{job_id}", dependencies=[auth])
    async def job(job_id: str) -> dict[str, Any]:
        try:
            return runtime.require_jobs().get(job_id).public()
        except KeyError as exc:
            raise ConsoleError("JOB_NOT_FOUND", "任务不存在", status_code=404) from exc

    @app.post("/api/jobs/{job_id}/cancel", dependencies=[auth])
    async def cancel_job(job_id: str) -> dict[str, Any]:
        try:
            runtime.require_jobs().cancel(job_id)
            return runtime.require_jobs().get(job_id).public()
        except KeyError as exc:
            raise ConsoleError("JOB_NOT_FOUND", "任务不存在", status_code=404) from exc

    @app.api_route("/api/{unknown_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"], dependencies=[auth])
    async def unknown_api(unknown_path: str) -> dict[str, Any]:
        raise ConsoleError("NOT_FOUND", f"API 路径不存在：/api/{unknown_path}", status_code=404)

    static_path = Path(static_dir).expanduser().resolve(strict=False) if static_dir else None
    if static_path and static_path.exists() and (static_path / "index.html").exists():
        app.mount("/", StaticFiles(directory=static_path, html=True), name="console-web")

    @app.exception_handler(404)
    async def not_found_handler(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": {"code": "NOT_FOUND", "message": "页面不存在"}})

    return app


def _constant_time_equal(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def _command_summary(root: Path, command: list[str]) -> str:
    safe: list[str] = ["aitest"]
    for value in command[3:]:
        try:
            path = Path(value)
            if path.is_absolute():
                safe.append(path.relative_to(root).as_posix())
                continue
        except (ValueError, OSError):
            pass
        safe.append(value)
    return " ".join(safe)
