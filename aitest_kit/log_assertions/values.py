"""Validate and freeze JSON inputs used by deferred checks."""
from __future__ import annotations

import json
import math
import re
from typing import Any

MAX_EXPECTED_BYTES = 65536


class LogInputError(ValueError):
    code = "LOG_INPUT_ERROR"


def safe_copy(value: Any, *, depth: int = 0) -> Any:
    if depth > 64:
        raise LogInputError("JSON input exceeds maximum nesting or contains a cycle")
    kind = type(value)
    if kind in (type(None), bool, str, int):
        return value
    if kind is float and math.isfinite(value):
        return value
    if kind is list:
        return [safe_copy(item, depth=depth + 1) for item in value]
    if kind is dict and all(type(key) is str for key in value):
        return {key: safe_copy(item, depth=depth + 1) for key, item in value.items()}
    raise LogInputError("expected a safe JSON value")


def sensitive_name(name: str) -> bool:
    key = re.sub(r"[^a-z0-9]", "", name.lower())
    return key in {
        "authorization", "password", "passwd", "secret", "credential", "credentials",
        "token", "accesstoken", "refreshtoken", "authtoken", "bearertoken", "sessiontoken",
        "apikey", "privatekey", "clientsecret", "cookie", "setcookie",
    } or key.endswith(("password", "secret", "apikey", "privatekey", "token"))


def freeze_expected(values: Any) -> Any:
    remaining = MAX_EXPECTED_BYTES

    def spend(size):
        nonlocal remaining
        remaining -= size
        if remaining < 0:
            raise LogInputError("expected JSON exceeds 65536 bytes")

    def copy(value, depth=0):
        if depth > 64:
            raise LogInputError("JSON input exceeds maximum nesting or contains a cycle")
        spend(1)
        kind = type(value)
        if kind is str:
            spend(len(value))
            return value
        if kind is list:
            return [copy(item, depth + 1) for item in value]
        if kind is dict:
            result = {}
            for key, item in value.items():
                if type(key) is not str:
                    raise LogInputError("expected a safe JSON value")
                spend(len(key) + 1)
                if sensitive_name(key):
                    raise LogInputError("sensitive expected fields cannot be frozen")
                result[key] = copy(item, depth + 1)
            return result
        if kind is int:
            spend(max(0, (value.bit_length() - 1) // 4))
        return safe_copy(value, depth=depth)

    frozen = copy(values)
    try:
        encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False)
        size = sum(len(chunk.encode("utf-8")) for chunk in encoder.iterencode(frozen))
    except (UnicodeError, ValueError) as exc:
        raise LogInputError("cannot encode expected JSON") from exc
    if size > MAX_EXPECTED_BYTES:
        raise LogInputError("expected JSON exceeds 65536 bytes")
    return frozen


def pointer_parts(pointer: str) -> list[str]:
    if not isinstance(pointer, str) or (pointer and not pointer.startswith("/")):
        raise LogInputError("expected a JSON Pointer")
    if re.search(r"~(?![01])", pointer):
        raise LogInputError("invalid JSON Pointer escape")
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:]]


def resolve_pointer(response: Any, pointer: str) -> Any:
    try:
        for part in pointer_parts(pointer):
            if sensitive_name(part):
                raise LogInputError("sensitive response fields cannot be frozen")
            if type(response) is dict:
                response = response[part]
            elif type(response) is list and re.fullmatch(r"0|[1-9][0-9]*", part):
                if len(part) > len(str(len(response))):
                    raise IndexError()
                response = response[int(part)]
            else:
                raise LookupError()
    except LookupError as exc:
        raise LogInputError(f"response JSON Pointer {pointer!r} is unavailable") from exc
    return response


def expected_provider(value: Any) -> dict[str, Any]:
    kinds = {"from_var", "from_response", "literal"}
    if isinstance(value, dict) and kinds.intersection(value):
        if len(value) != 1:
            raise LogInputError("expected provider must contain exactly one key")
        kind, item = next(iter(value.items()))
        if kind == "from_var" and (not isinstance(item, str) or not item.isidentifier()):
            raise LogInputError("from_var must name a profile variable")
        if kind == "from_response":
            pointer_parts(item)
        if kind == "literal":
            freeze_expected(item)
        return {kind: item}
    return {"literal": freeze_expected(value)}
