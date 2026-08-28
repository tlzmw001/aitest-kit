"""Configuration references for the local Pi worker."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

import yaml


_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
AGENT_PROTOCOLS = {
    "auto",
    "openai_responses",
    "openai_chat_completions",
    "anthropic_messages",
}
_SAFE_CHILD_ENV = (
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "NODE_EXTRA_CA_CERTS",
    "PATH",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "TMPDIR",
)


class AgentConfigError(RuntimeError):
    """Raised when the workspace Agent configuration is missing or unsafe."""


@dataclass(frozen=True)
class AgentModelConfig:
    provider: str
    name: str
    api_key_env: str
    protocol: str = "auto"
    base_url: str | None = None
    base_url_env: str | None = None


@dataclass(frozen=True)
class AgentConfig:
    runtime: str
    model: AgentModelConfig
    connection_name: str = ""


def load_agent_config(workspace: str | Path) -> AgentConfig:
    config_path = Path(workspace).expanduser().resolve() / "aitest_config" / "aitest.yaml"
    if not config_path.is_file():
        raise AgentConfigError(f"Agent 配置文件不存在: {config_path}")
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001 - configuration diagnostics preserve the loader failure.
        raise AgentConfigError(f"无法读取 Agent 配置: {exc}") from exc
    if not isinstance(data, dict):
        raise AgentConfigError("AITest 配置必须是 YAML mapping")
    agent = data.get("agent")
    if not isinstance(agent, dict):
        raise AgentConfigError("缺少 agent 配置")
    forbidden_agent = sorted(key for key in agent if key in {"api_key", "token", "secret", "password"})
    if forbidden_agent:
        raise AgentConfigError(f"agent 禁止保存敏感字段: {', '.join(forbidden_agent)}")
    runtime = _required_string(agent, "runtime", "agent")
    if runtime != "pi":
        raise AgentConfigError(f"不支持的 Agent runtime: {runtime}")
    model = agent.get("model")
    if not isinstance(model, dict):
        raise AgentConfigError("缺少 agent.model 配置")
    forbidden = sorted(key for key in model if key in {"api_key", "token", "secret", "password"})
    if forbidden:
        raise AgentConfigError(f"agent.model 禁止保存敏感字段: {', '.join(forbidden)}")
    provider = _required_string(model, "provider", "agent.model")
    name = _required_string(model, "name", "agent.model")
    protocol = str(model.get("protocol") or "auto").strip()
    if protocol not in AGENT_PROTOCOLS:
        raise AgentConfigError(f"不支持的 agent.model.protocol: {protocol}")
    api_key_env = _environment_name(model.get("api_key_env"), "agent.model.api_key_env")
    raw_base_url = model.get("base_url")
    base_url = None
    if raw_base_url not in (None, ""):
        if not isinstance(raw_base_url, str):
            raise AgentConfigError("agent.model.base_url 必须是字符串")
        base_url = _base_url(raw_base_url)
    raw_base_url_env = model.get("base_url_env")
    base_url_env = None
    if raw_base_url_env not in (None, ""):
        base_url_env = _environment_name(raw_base_url_env, "agent.model.base_url_env")
    return AgentConfig(
        runtime=runtime,
        connection_name=str(agent.get("connection_name") or "").strip(),
        model=AgentModelConfig(
            provider=provider,
            name=name,
            api_key_env=api_key_env,
            protocol=protocol,
            base_url=base_url,
            base_url_env=base_url_env,
        ),
    )


def build_worker_environment(
    config: AgentConfig,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build the explicit environment inherited by the Node worker."""
    source = environ if environ is not None else os.environ
    allowed = set(_SAFE_CHILD_ENV)
    allowed.add(config.model.api_key_env)
    if config.model.base_url_env:
        allowed.add(config.model.base_url_env)
        if source.get(config.model.base_url_env):
            _base_url(source[config.model.base_url_env])
    child = {name: source[name] for name in sorted(allowed) if source.get(name) is not None}
    child["PYTHONUNBUFFERED"] = "1"
    return child


def _required_string(mapping: dict, key: str, scope: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AgentConfigError(f"{scope}.{key} 必须是非空字符串")
    return value.strip()


def _environment_name(value: object, field: str) -> str:
    if not isinstance(value, str) or not _ENV_NAME.fullmatch(value):
        raise AgentConfigError(f"{field} 必须是合法的环境变量名")
    return value


def _base_url(value: str) -> str:
    normalized = value.strip()
    parsed = urlsplit(normalized)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise AgentConfigError("agent.model.base_url 必须是安全的绝对 HTTP(S) 地址")
    return normalized.rstrip("/")
