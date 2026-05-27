"""Runtime resolution for generated pytest profile variables."""
from __future__ import annotations

import os
from typing import Any


class ProfileVariableError(AssertionError):
    """Raised when generated tests cannot resolve declared profile variables."""

    def __init__(self, message: str, *, missing_env: list[str] | None = None) -> None:
        super().__init__(message)
        self.missing_env = list(missing_env or [])


def resolve_profile_variables(specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Resolve generated profile variable specs without leaking environment values."""
    values: dict[str, Any] = {}
    missing_env: list[str] = []

    for name, spec in specs.items():
        if not isinstance(spec, dict):
            raise ProfileVariableError(f"profile variable {name} spec must be a mapping")
        if "env" in spec:
            env_name = spec["env"]
            if not isinstance(env_name, str) or not env_name:
                raise ProfileVariableError(f"profile variable {name} env must be a non-empty string")
            if env_name not in os.environ:
                missing_env.append(env_name)
                continue
            values[name] = os.environ[env_name]
            continue
        if "value" in spec:
            values[name] = spec["value"]
            continue
        raise ProfileVariableError(f"profile variable {name} must declare env or value")

    if missing_env:
        missing_names = sorted(set(missing_env))
        missing = ", ".join(missing_names)
        raise ProfileVariableError(
            f"profile variable environment missing: {missing}",
            missing_env=missing_names,
        )

    return values
