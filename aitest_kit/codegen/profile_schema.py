"""JSON Schema validation helpers for codegen profiles."""
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


_PROFILE_SCHEMA_RELATIVE_PATH = Path("aitest_config/schemas/codegen_profile.schema.json")
_REPO_PROFILE_SCHEMA_PATH = Path(__file__).resolve().parents[2] / _PROFILE_SCHEMA_RELATIVE_PATH
_PACKAGE_PROFILE_SCHEMA = "aitest_kit.templates.project_workspace"


def profile_schema_diagnostics(data: dict[str, Any]) -> list[tuple[str, str]]:
    """Return profile schema diagnostics as (message, source) pairs."""
    try:
        validator = _profile_schema_validator()
    except Exception as exc:
        try:
            _, source = _profile_schema_source()
        except Exception:
            source = str(_profile_schema_path())
        return [(f"profile JSON Schema is unavailable: {exc}", source)]

    return [
        (_format_schema_error(error), _schema_error_source(error))
        for error in sorted(validator.iter_errors(data), key=_schema_error_sort_key)
    ]


def _profile_schema_validator() -> Draft202012Validator:
    schema_text, _ = _profile_schema_source()
    schema = json.loads(schema_text)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _profile_schema_path() -> Path:
    cwd_schema = _PROFILE_SCHEMA_RELATIVE_PATH
    return cwd_schema if cwd_schema.exists() else _REPO_PROFILE_SCHEMA_PATH


def _profile_schema_source() -> tuple[str, str]:
    cwd_schema = _PROFILE_SCHEMA_RELATIVE_PATH
    if cwd_schema.exists():
        return cwd_schema.read_text(encoding="utf-8"), str(cwd_schema)
    if _REPO_PROFILE_SCHEMA_PATH.exists():
        return _REPO_PROFILE_SCHEMA_PATH.read_text(encoding="utf-8"), str(_REPO_PROFILE_SCHEMA_PATH)
    resource = resources.files(_PACKAGE_PROFILE_SCHEMA).joinpath(
        "aitest_config",
        "schemas",
        "codegen_profile.schema.json",
    )
    return resource.read_text(encoding="utf-8"), str(resource)


def _schema_error_sort_key(error: ValidationError) -> tuple[str, str]:
    return (_schema_error_source(error), error.message)


def _schema_error_source(error: ValidationError) -> str:
    parts: list[str] = []
    for part in error.absolute_path:
        if isinstance(part, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{part}]"
            else:
                parts.append(f"[{part}]")
        else:
            parts.append(str(part))
    return ".".join(parts) or "<root>"


def _format_schema_error(error: ValidationError) -> str:
    return f"profile schema violation: {error.message}"
