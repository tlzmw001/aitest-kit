from __future__ import annotations

from pathlib import Path

import pytest

from aitest_kit.agent.config import AgentConfigError, build_worker_environment, load_agent_config


def write_config(workspace: Path, body: str) -> None:
    config_dir = workspace / "aitest_config"
    config_dir.mkdir(parents=True)
    (config_dir / "aitest.yaml").write_text(body, encoding="utf-8")


def test_load_agent_config_keeps_only_environment_variable_references(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        """
agent:
  runtime: pi
  model:
    provider: anthropic
    name: claude-sonnet-4-5
    api_key_env: ANTHROPIC_API_KEY
    base_url_env: ANTHROPIC_BASE_URL
""",
    )

    config = load_agent_config(tmp_path)

    assert config.runtime == "pi"
    assert config.model.provider == "anthropic"
    assert config.model.name == "claude-sonnet-4-5"
    assert config.model.api_key_env == "ANTHROPIC_API_KEY"
    assert not hasattr(config.model, "api_key")


def test_load_agent_config_accepts_public_protocol_and_nonsecret_base_url(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        """
agent:
  runtime: pi
  connection_name: Local gateway
  model:
    protocol: openai_responses
    provider: openai
    name: gpt-5.5
    api_key_env: LOCAL_GATEWAY_API_KEY
    base_url: https://gateway.example.test
    base_url_env: null
""",
    )

    config = load_agent_config(tmp_path)

    assert config.connection_name == "Local gateway"
    assert config.model.protocol == "openai_responses"
    assert config.model.base_url == "https://gateway.example.test"


def test_load_agent_config_rejects_unsupported_protocol(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        """
agent:
  runtime: pi
  model:
    protocol: imaginary_api
    provider: openai
    name: gpt-5.5
    api_key_env: OPENAI_API_KEY
""",
    )

    with pytest.raises(AgentConfigError, match="protocol"):
        load_agent_config(tmp_path)


def test_load_agent_config_rejects_unsafe_base_url(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        """
agent:
  runtime: pi
  model:
    protocol: openai_responses
    provider: openai
    name: gpt-5.5
    api_key_env: OPENAI_API_KEY
    base_url: https://user:secret@gateway.example.test#credentials
""",
    )

    with pytest.raises(AgentConfigError, match="base_url"):
        load_agent_config(tmp_path)


def test_load_agent_config_rejects_literal_secret_field(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        """
agent:
  runtime: pi
  model:
    provider: anthropic
    name: claude-sonnet-4-5
    api_key: sk-forbidden
    api_key_env: ANTHROPIC_API_KEY
""",
    )

    with pytest.raises(AgentConfigError, match="api_key"):
        load_agent_config(tmp_path)


def test_load_agent_config_rejects_literal_secret_at_agent_scope(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        """
agent:
  runtime: pi
  token: forbidden
  model:
    provider: anthropic
    name: claude-sonnet-4-5
    api_key_env: ANTHROPIC_API_KEY
""",
    )

    with pytest.raises(AgentConfigError, match="token"):
        load_agent_config(tmp_path)


def test_build_worker_environment_uses_explicit_allowlist(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        """
agent:
  runtime: pi
  model:
    provider: anthropic
    name: claude-sonnet-4-5
    api_key_env: ANTHROPIC_API_KEY
""",
    )
    config = load_agent_config(tmp_path)
    environ = {
        "PATH": "/usr/bin",
        "HOME": "/Users/tester",
        "LANG": "en_US.UTF-8",
        "ANTHROPIC_API_KEY": "secret-key",
        "DATABASE_URL": "must-not-leak",
        "UNRELATED_TOKEN": "must-not-leak-either",
    }

    child_env = build_worker_environment(config, environ=environ)

    assert child_env["ANTHROPIC_API_KEY"] == "secret-key"
    assert child_env["PATH"] == "/usr/bin"
    assert child_env["HOME"] == "/Users/tester"
    assert "DATABASE_URL" not in child_env
    assert "UNRELATED_TOKEN" not in child_env


def test_build_worker_environment_rejects_unsafe_base_url_environment(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        """
agent:
  runtime: pi
  model:
    provider: openai
    name: gpt-5.5
    api_key_env: OPENAI_API_KEY
    base_url_env: OPENAI_BASE_URL
""",
    )
    config = load_agent_config(tmp_path)

    with pytest.raises(AgentConfigError, match="base_url"):
        build_worker_environment(
            config,
            environ={
                "OPENAI_API_KEY": "secret-key",
                "OPENAI_BASE_URL": "https://user:secret@gateway.example.test",
            },
        )
