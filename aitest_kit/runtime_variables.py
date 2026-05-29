"""Runtime resolution for generated pytest profile variables."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable


AITEST_ENV_FILE = "AITEST_ENV_FILE"


class ProfileVariableError(AssertionError):
    """Raised when generated tests cannot resolve declared profile variables."""

    def __init__(self, message: str, *, missing_env: list[str] | None = None) -> None:
        super().__init__(message)
        self.missing_env = list(missing_env or [])


class PreconditionMissing(ProfileVariableError):
    """Raised when a fixture cannot satisfy required runtime preconditions."""


def require_env(name: str) -> str:
    """Return a required env value or raise a report-classifiable precondition error."""
    if not isinstance(name, str) or not name:
        raise PreconditionMissing("required environment variable name must be a non-empty string")
    value = os.environ.get(name)
    if value:
        return value
    dotenv = load_dotenv_values()
    value = dotenv.get(name)
    if value:
        return value
    raise PreconditionMissing(
        f"profile variable environment missing: {name}",
        missing_env=[name],
    )


def require_envs(names: Iterable[str]) -> dict[str, str]:
    """Return multiple required env values and report all missing names together."""
    values: dict[str, str] = {}
    missing: list[str] = []
    dotenv = load_dotenv_values()

    for name in names:
        if not isinstance(name, str) or not name:
            raise PreconditionMissing("required environment variable name must be a non-empty string")
        value = os.environ.get(name)
        if not value:
            value = dotenv.get(name)
        if value:
            values[name] = value
        else:
            missing.append(name)

    if missing:
        missing_names = sorted(set(missing))
        raise PreconditionMissing(
            f"profile variable environment missing: {', '.join(missing_names)}",
            missing_env=missing_names,
        )
    return values


def resolve_profile_variables(specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Resolve generated profile variable specs without leaking environment values."""
    values: dict[str, Any] = {}
    missing_env: list[str] = []
    dotenv = load_dotenv_values()

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


def load_dotenv_values(
    *,
    strict_configured: bool = False,
    paths: Iterable[str | Path] | None = None,
) -> dict[str, str]:
    """Load the configured AITest dotenv file without overriding process env."""
    dotenv_paths = [Path(path).expanduser() for path in paths] if paths is not None else _dotenv_paths()
    values: dict[str, str] = {}
    configured = is_dotenv_configured() or paths is not None
    for path in dotenv_paths:
        if not path.exists() or not path.is_file():
            if strict_configured and configured:
                raise ProfileVariableError(f"env file not found: {path}")
            continue
        values.update(_parse_dotenv(path))
    return values


def dotenv_path() -> Path:
    configured = os.environ.get(AITEST_ENV_FILE)
    if configured:
        return Path(configured).expanduser()
    return Path.cwd() / ".env"


def is_dotenv_configured() -> bool:
    return bool(os.environ.get(AITEST_ENV_FILE))


def _dotenv_paths() -> list[Path]:
    return [dotenv_path()]


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
