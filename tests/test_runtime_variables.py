from __future__ import annotations

import pytest

from aitest_kit.runtime_variables import ProfileVariableError, resolve_profile_variables


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
