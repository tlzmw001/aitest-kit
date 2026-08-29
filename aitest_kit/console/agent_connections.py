from __future__ import annotations

import os
import re
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

import yaml
from fastapi import APIRouter, Response
from pydantic import BaseModel, Field, SecretStr

from aitest_kit.agent.client import AgentWorkerError, WorkerClient, default_worker_command
from aitest_kit.agent.config import AGENT_PROTOCOLS, AgentConfigError, build_worker_environment, load_agent_config
from aitest_kit.agent.protocol import redact
from aitest_kit.console.errors import ConsoleError


_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PROVIDER_BY_PROTOCOL = {
    "openai_responses": "openai",
    "openai_chat_completions": "aitest-openai-chat",
    "anthropic_messages": "anthropic",
}
_SESSION_API_KEY_ENV = "AITEST_AGENT_SESSION_API_KEY"
_MAX_API_KEY_LENGTH = 4096


class AgentConnectionPayload(BaseModel):
    connection_name: str = Field(max_length=80)
    protocol: str = Field(max_length=48)
    base_url: str = Field(default="", max_length=2048)
    model: str = Field(max_length=160)
    api_key_env: str = Field(default="AITEST_AGENT_API_KEY", max_length=160)
    api_key: Optional[SecretStr] = None


@dataclass(frozen=True)
class AgentConnectionAttempt:
    workspace: Path
    protocol: str
    provider: str
    base_url: str
    model: str
    api_key: str


@dataclass(frozen=True)
class AgentRuntimeLaunch:
    initialize_payload: dict[str, Any]
    environment: dict[str, str]


class AgentConnectionAttemptError(RuntimeError):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


ConnectionTester = Callable[[AgentConnectionAttempt], str]


class AgentConnectionService:
    def __init__(self, tester: ConnectionTester | None = None) -> None:
        self._tester = tester or test_pi_connection
        self._session_keys: dict[Path, str] = {}

    def get(self, workspace: str | Path) -> dict[str, Any]:
        root = Path(workspace).resolve()
        data = self._read_agent_mapping(root)
        model = data.get("model") if isinstance(data.get("model"), dict) else {}
        api_key_env = str(model.get("api_key_env") or "AITEST_AGENT_API_KEY")
        session_key = self._session_keys.get(root)
        environment_key = os.environ.get(api_key_env)
        credential_source = "session" if session_key else "environment" if environment_key else "missing"
        return {
            "connection_name": str(data.get("connection_name") or ""),
            "protocol": str(model.get("protocol") or "auto"),
            "base_url": _validate_base_url(str(model.get("base_url") or "")),
            "model": str(model.get("name") or ""),
            "api_key_env": api_key_env,
            "has_api_key": credential_source != "missing",
            "credential_source": credential_source,
        }

    def save(self, workspace: str | Path, payload: AgentConnectionPayload | Mapping[str, Any]) -> dict[str, Any]:
        root = Path(workspace).resolve()
        values = self._normalize(payload)
        provider = _provider_for_protocol(values["protocol"], values["model"])
        agent = {
            "runtime": "pi",
            "connection_name": values["connection_name"],
            "model": {
                "protocol": values["protocol"],
                "provider": provider,
                "name": values["model"],
                "api_key_env": values["api_key_env"],
                "base_url": values["base_url"] or None,
                "base_url_env": None,
            },
        }
        self._write_agent_mapping(root, agent)
        if values["api_key"]:
            self._session_keys[root] = values["api_key"]
        return self.get(root)

    def test(self, workspace: str | Path, payload: AgentConnectionPayload | Mapping[str, Any]) -> dict[str, Any]:
        root = Path(workspace).resolve()
        values = self._normalize(payload)
        api_key = values["api_key"] or self._session_keys.get(root) or os.environ.get(values["api_key_env"], "")
        if not api_key:
            raise ConsoleError("AGENT_API_KEY_REQUIRED", "请输入 API Key，或设置对应环境变量", status_code=422)
        started = time.monotonic()
        for protocol in _protocol_candidates(values["protocol"], values["model"]):
            attempt = AgentConnectionAttempt(
                workspace=root,
                protocol=protocol,
                provider=_PROVIDER_BY_PROTOCOL[protocol],
                base_url=values["base_url"],
                model=values["model"],
                api_key=api_key,
            )
            try:
                response_text = self._tester(attempt)
                return {
                    "status": "connected",
                    "detected_protocol": protocol,
                    "internal_provider": attempt.provider,
                    "model": values["model"],
                    "response_text": response_text,
                    "latency_ms": round((time.monotonic() - started) * 1000),
                }
            except AgentConnectionAttemptError as exc:
                if exc.kind == "protocol_mismatch" and values["protocol"] == "auto":
                    continue
                _raise_console_attempt_error(exc, api_key)
        raise ConsoleError("AGENT_PROTOCOL_UNDETECTED", "无法识别该服务支持的模型接口", status_code=422)

    def clear_session_keys(self) -> None:
        self._session_keys.clear()

    def runtime_launch(self, workspace: str | Path, *, permission_mode: str) -> AgentRuntimeLaunch:
        root = Path(workspace).resolve()
        try:
            config = load_agent_config(root)
        except AgentConfigError as exc:
            raise ConsoleError("AGENT_CONFIG_INVALID", str(exc), status_code=422) from exc
        api_key = self._session_keys.get(root) or os.environ.get(config.model.api_key_env, "")
        if not api_key:
            raise ConsoleError("AGENT_API_KEY_REQUIRED", "请先配置 API Key，或设置对应环境变量", status_code=422)
        source_environment = dict(os.environ)
        source_environment[config.model.api_key_env] = api_key
        try:
            environment = build_worker_environment(config, environ=source_environment)
        except AgentConfigError as exc:
            raise ConsoleError("AGENT_CONFIG_INVALID", str(exc), status_code=422) from exc
        skill_paths = [
            str(candidate)
            for relative in (".codex/skills", ".agents/skills", "skills")
            if (candidate := root / relative).is_dir()
        ]
        return AgentRuntimeLaunch(
            initialize_payload={
                "cwd": str(root),
                "model": {
                    "protocol": config.model.protocol,
                    "provider": config.model.provider,
                    "name": config.model.name,
                    "api_key_env": config.model.api_key_env,
                    "base_url": config.model.base_url,
                    "base_url_env": config.model.base_url_env,
                },
                "skill_paths": skill_paths,
                "tools": ["read", "write", "edit", "grep", "find", "ls", "bash"],
                "permission_mode": permission_mode,
            },
            environment=environment,
        )

    def _normalize(self, payload: AgentConnectionPayload | Mapping[str, Any]) -> dict[str, str]:
        raw = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict() if hasattr(payload, "dict") else dict(payload)
        connection_name = str(raw.get("connection_name") or "").strip()
        protocol = str(raw.get("protocol") or "auto").strip()
        base_url = _validate_base_url(str(raw.get("base_url") or "").strip())
        model = str(raw.get("model") or "").strip()
        api_key_env = str(raw.get("api_key_env") or "AITEST_AGENT_API_KEY").strip()
        raw_api_key = raw.get("api_key")
        api_key = raw_api_key.get_secret_value().strip() if isinstance(raw_api_key, SecretStr) else str(raw_api_key or "").strip()
        if not connection_name:
            raise ConsoleError("AGENT_CONNECTION_NAME_REQUIRED", "请输入连接名称", status_code=422)
        if protocol not in AGENT_PROTOCOLS:
            raise ConsoleError("AGENT_PROTOCOL_INVALID", "接口类型不受支持", status_code=422)
        if not model:
            raise ConsoleError("AGENT_MODEL_REQUIRED", "请输入模型名称", status_code=422)
        if not _ENV_NAME.fullmatch(api_key_env):
            raise ConsoleError("AGENT_API_KEY_ENV_INVALID", "API Key 环境变量名不合法", status_code=422)
        if len(api_key) > _MAX_API_KEY_LENGTH:
            raise ConsoleError("AGENT_API_KEY_INVALID", "API Key 长度超过限制", status_code=422)
        return {
            "connection_name": connection_name,
            "protocol": protocol,
            "base_url": base_url,
            "model": model,
            "api_key_env": api_key_env,
            "api_key": api_key,
        }

    @staticmethod
    def _read_agent_mapping(root: Path) -> dict[str, Any]:
        config_path = root / "aitest_config" / "aitest.yaml"
        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ConsoleError("AGENT_CONFIG_INVALID", f"无法读取 Agent 配置: {exc}") from exc
        agent = data.get("agent") if isinstance(data, dict) else None
        return dict(agent) if isinstance(agent, dict) else {}

    @staticmethod
    def _write_agent_mapping(root: Path, agent: dict[str, Any]) -> None:
        config_path = root / "aitest_config" / "aitest.yaml"
        try:
            original = config_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConsoleError("AGENT_CONFIG_WRITE_FAILED", f"无法读取配置文件: {exc}") from exc
        replacement = yaml.safe_dump({"agent": agent}, allow_unicode=True, sort_keys=False).rstrip() + "\n"
        updated = _replace_top_level_block(original, "agent", replacement)
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=config_path.parent,
                prefix=".aitest-agent-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(updated)
                temporary = Path(handle.name)
            os.chmod(temporary, config_path.stat().st_mode)
            os.replace(temporary, config_path)
        except OSError as exc:
            if "temporary" in locals():
                temporary.unlink(missing_ok=True)
            raise ConsoleError("AGENT_CONFIG_WRITE_FAILED", f"无法保存 Agent 配置: {exc}") from exc


def create_agent_connection_router(
    service: AgentConnectionService,
    workspace_root: Callable[[], Path],
) -> APIRouter:
    router = APIRouter(prefix="/api/agent")

    @router.get("/connection")
    async def get_connection(response: Response) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return service.get(workspace_root())

    @router.put("/connection")
    async def save_connection(payload: AgentConnectionPayload, response: Response) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return service.save(workspace_root(), payload)

    @router.post("/connection/test")
    async def test_connection(payload: AgentConnectionPayload, response: Response) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return service.test(workspace_root(), payload)

    return router


def test_pi_connection(attempt: AgentConnectionAttempt) -> str:
    env = {name: value for name, value in os.environ.items() if name in {"HOME", "LANG", "LC_ALL", "LC_CTYPE", "PATH", "SYSTEMROOT", "TEMP", "TMP", "TMPDIR"}}
    env[_SESSION_API_KEY_ENV] = attempt.api_key
    with WorkerClient(default_worker_command(), env=env, startup_timeout=20, message_timeout=90) as client:
        client.start({
            "cwd": str(attempt.workspace),
            "model": {
                "protocol": attempt.protocol,
                "provider": attempt.provider,
                "name": attempt.model,
                "api_key_env": _SESSION_API_KEY_ENV,
                "base_url": attempt.base_url or None,
            },
            "skill_paths": [],
            "tools": [],
            "permission_mode": "approval",
        })
        try:
            events = client.run_prompt(
                "Reply with exactly OK. Do not call tools.",
                approval_handler=lambda _event: "deny",
            )
        except AgentWorkerError as exc:
            message = _redact_exact(str(exc), attempt.api_key)
            details = _redact_exact(str(redact(exc.details)), attempt.api_key)
            raise AgentConnectionAttemptError(_classify_worker_error(message, details), message) from exc
    text = "".join(str(event.payload.get("delta", "")) for event in events if event.type == "text_delta").strip()
    if not text:
        raise AgentConnectionAttemptError("service", "模型没有返回文本")
    return text[:1000]


def _provider_for_protocol(protocol: str, model: str) -> str:
    resolved = _protocol_candidates(protocol, model)[0]
    return _PROVIDER_BY_PROTOCOL[resolved]


def _protocol_candidates(protocol: str, model: str) -> list[str]:
    if protocol != "auto":
        return [protocol]
    if model.lower().startswith("claude"):
        return ["anthropic_messages", "openai_chat_completions"]
    return ["openai_responses", "openai_chat_completions"]


def _validate_base_url(value: str) -> str:
    if not value:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.fragment:
        raise ConsoleError("AGENT_BASE_URL_INVALID", "Base URL 必须是安全的绝对 HTTP(S) 地址", status_code=422)
    return value.rstrip("/")


def _replace_top_level_block(original: str, key: str, replacement: str) -> str:
    lines = original.splitlines(keepends=True)
    start = next((index for index, line in enumerate(lines) if re.match(rf"^{re.escape(key)}\s*:", line)), None)
    if start is None:
        separator = "" if not original or original.endswith("\n\n") else "\n"
        return original + separator + replacement
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.strip() and not line.startswith((" ", "\t", "#")):
            end = index
            break
    trailing = end
    while trailing > start + 1:
        candidate = lines[trailing - 1]
        if candidate.strip() and not candidate.startswith("#"):
            break
        trailing -= 1
    return "".join(lines[:start]) + replacement + "".join(lines[trailing:])


def _classify_worker_error(message: str, details: str) -> str:
    rendered = f"{message} {details}".lower()
    if any(token in rendered for token in ("401", "403", "unauthorized", "invalid api key", "authentication")):
        return "authentication"
    if any(token in rendered for token in ("429", "quota", "rate limit")):
        return "rate_limit"
    if any(token in rendered for token in ("404", "405", "not found", "unsupported endpoint")):
        return "protocol_mismatch"
    if "timeout" in rendered or "超时" in rendered:
        return "timeout"
    return "service"


def _raise_console_attempt_error(exc: AgentConnectionAttemptError, api_key: str) -> None:
    message = _redact_exact(str(exc), api_key)
    mapping = {
        "authentication": ("AGENT_AUTHENTICATION_FAILED", 401),
        "rate_limit": ("AGENT_RATE_LIMITED", 429),
        "protocol_mismatch": ("AGENT_PROTOCOL_MISMATCH", 422),
        "timeout": ("AGENT_CONNECTION_TIMEOUT", 504),
        "service": ("AGENT_CONNECTION_FAILED", 502),
    }
    code, status = mapping.get(exc.kind, mapping["service"])
    raise ConsoleError(code, message, status_code=status) from exc


def _redact_exact(value: str, secret: str) -> str:
    safe = str(redact(value))
    return safe.replace(secret, "[REDACTED]") if secret else safe
