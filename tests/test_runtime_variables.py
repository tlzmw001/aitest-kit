from __future__ import annotations

import pytest

from aitest_kit.runtime_variables import (
    PreconditionMissing,
    ProfileVariableError,
    load_dotenv_values,
    require_env,
    require_envs,
    resolve_profile_variables,
)


def test_resolve_profile_variables_reads_env_and_literals(monkeypatch):
    monkeypatch.setenv("AITEST_USER", "user@example.test")

    values = resolve_profile_variables({
        "username": {"env": "AITEST_USER"},
        "password": {"value": "wrong-password"},
    })

    assert values == {
        "username": "user@example.test",
        "password": "wrong-password",
    }


def test_resolve_profile_variables_reports_missing_env_name_only(monkeypatch):
    monkeypatch.delenv("AITEST_TOKEN", raising=False)

    with pytest.raises(ProfileVariableError) as exc_info:
        resolve_profile_variables({"token": {"env": "AITEST_TOKEN"}})

    assert exc_info.value.missing_env == ["AITEST_TOKEN"]
    assert "AITEST_TOKEN" in str(exc_info.value)


def test_resolve_profile_variables_reads_current_directory_dotenv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AITEST_TOKEN", raising=False)
    (tmp_path / ".env").write_text(
        """
# local test values
AITEST_TOKEN=token-from-dotenv
AITEST_QUOTED="quoted value"
export AITEST_EXPORTED=exported-value
""",
        encoding="utf-8",
    )

    values = resolve_profile_variables({
        "token": {"env": "AITEST_TOKEN"},
        "quoted": {"env": "AITEST_QUOTED"},
        "exported": {"env": "AITEST_EXPORTED"},
    })

    assert values == {
        "token": "token-from-dotenv",
        "quoted": "quoted value",
        "exported": "exported-value",
    }


def test_resolve_profile_variables_os_environ_overrides_dotenv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AITEST_TOKEN", "token-from-env")
    (tmp_path / ".env").write_text("AITEST_TOKEN=token-from-dotenv\n", encoding="utf-8")

    values = resolve_profile_variables({"token": {"env": "AITEST_TOKEN"}})

    assert values == {"token": "token-from-env"}


def test_resolve_profile_variables_reads_configured_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / "local.env"
    env_file.write_text("AITEST_TOKEN=token-from-configured-file\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "..")
    monkeypatch.delenv("AITEST_TOKEN", raising=False)
    monkeypatch.setenv("AITEST_ENV_FILE", str(env_file))

    values = resolve_profile_variables({"token": {"env": "AITEST_TOKEN"}})

    assert values == {"token": "token-from-configured-file"}


def test_load_dotenv_values_rejects_missing_configured_env_file(tmp_path, monkeypatch):
    missing = tmp_path / "missing.env"
    monkeypatch.setenv("AITEST_ENV_FILE", str(missing))

    with pytest.raises(ProfileVariableError) as exc_info:
        load_dotenv_values(strict_configured=True)

    assert str(missing) in str(exc_info.value)


def test_require_env_reads_process_environment(monkeypatch):
    monkeypatch.setenv("AITEST_TOKEN", "token-from-env")

    assert require_env("AITEST_TOKEN") == "token-from-env"


def test_require_env_reads_configured_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / "local.env"
    env_file.write_text("AITEST_TOKEN=token-from-file\n", encoding="utf-8")
    monkeypatch.delenv("AITEST_TOKEN", raising=False)
    monkeypatch.setenv("AITEST_ENV_FILE", str(env_file))

    assert require_env("AITEST_TOKEN") == "token-from-file"


def test_require_env_reports_missing_env_name_only(monkeypatch):
    monkeypatch.delenv("AITEST_TOKEN", raising=False)
    monkeypatch.delenv("AITEST_ENV_FILE", raising=False)

    with pytest.raises(PreconditionMissing) as exc_info:
        require_env("AITEST_TOKEN")

    assert exc_info.value.missing_env == ["AITEST_TOKEN"]
    assert "AITEST_TOKEN" in str(exc_info.value)


def test_require_envs_reports_all_missing_names(monkeypatch):
    monkeypatch.setenv("AITEST_USER", "user@example.test")
    monkeypatch.delenv("AITEST_TOKEN", raising=False)
    monkeypatch.delenv("AITEST_BASE_URL", raising=False)
    monkeypatch.delenv("AITEST_ENV_FILE", raising=False)

    with pytest.raises(PreconditionMissing) as exc_info:
        require_envs(["AITEST_USER", "AITEST_TOKEN", "AITEST_BASE_URL"])

    assert exc_info.value.missing_env == ["AITEST_BASE_URL", "AITEST_TOKEN"]
