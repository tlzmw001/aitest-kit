"""Runtime resolution for generated pytest profile variables."""
from __future__ import annotations

import os
from pathlib import Path
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
    dotenv = _load_dotenv()

    for name, spec in specs.items():
        if not isinstance(spec, dict):
            raise ProfileVariableError(f"profile variable {name} spec must be a mapping")
        if "env" in spec:
            env_name = spec["env"]
            if not isinstance(env_name, str) or not env_name:
                raise ProfileVariableError(f"profile variable {name} env must be a non-empty string")
            if env_name in os.environ:
                values[name] = os.environ[env_name]
                continue
            if env_name in dotenv:
                values[name] = dotenv[env_name]
                continue
            missing_env.append(env_name)
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


def _load_dotenv() -> dict[str, str]:
    paths = _dotenv_paths()
    values: dict[str, str] = {}
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        values.update(_parse_dotenv(path))
    return values


def _dotenv_paths() -> list[Path]:
    configured = os.environ.get("AITEST_ENV_FILE")
    if configured:
        return [Path(configured).expanduser()]
    return [Path.cwd() / ".env"]


def _parse_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ProfileVariableError(f"cannot read profile variable env file: {path}") from exc

    for line_no, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            raise ProfileVariableError(f"invalid env file line {path}:{line_no}")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ProfileVariableError(f"invalid env file line {path}:{line_no}")
        values[key] = _strip_env_value(value.strip())
    return values


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
