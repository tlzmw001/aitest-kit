"""Shared request binding helpers used by generated pytest."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def deep_merge(base: Any, override: Any) -> Any:
    """Merge nested request values, merging lists by index."""
    if isinstance(base, dict) and isinstance(override, dict):
        result = deepcopy(base)
        for key, value in override.items():
            result[key] = deep_merge(result[key], value) if key in result else deepcopy(value)
        return result

    if isinstance(base, list) and isinstance(override, list):
        result: list[Any] = []
        for index in range(max(len(base), len(override))):
            if index < len(base) and index < len(override):
                result.append(deep_merge(base[index], override[index]))
            elif index < len(override):
                result.append(deepcopy(override[index]))
            else:
                result.append(deepcopy(base[index]))
        return result

    return deepcopy(override)


def build_request(
    base: dict[str, Any],
    *,
    auto_fields: dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
    patches: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a concrete request body from base data and profile binding."""
    request = deep_merge(deepcopy(base), auto_fields or {})
    request = deep_merge(request, overrides or {})
    return apply_json_patch(request, patches or [])


def apply_json_patch(document: Any, patches: list[dict[str, Any]]) -> Any:
    """Apply a small RFC 6902 subset: add, replace, remove."""
    result = deepcopy(document)
    for patch in patches:
        if not isinstance(patch, dict):
            raise ValueError("JSON Patch entry must be a mapping")
        op = patch.get("op")
        path = patch.get("path")
        if not isinstance(op, str) or not isinstance(path, str):
            raise ValueError("JSON Patch entry requires string op and path")
        if op == "add":
            if "value" not in patch:
                raise ValueError(f"JSON Patch add requires value at {path}")
            result = _patch_add(result, path, patch["value"])
        elif op == "replace":
            if "value" not in patch:
                raise ValueError(f"JSON Patch replace requires value at {path}")
            result = _patch_replace(result, path, patch["value"])
        elif op == "remove":
            if "value" in patch:
                raise ValueError(f"JSON Patch remove must not include value at {path}")
            result = _patch_remove(result, path)
        else:
            raise ValueError(f"unsupported JSON Patch op: {op}")
    return result


def _decode_pointer(path: str) -> list[str]:
    if path == "":
        return []
    if not path.startswith("/"):
        raise ValueError(f"JSON Pointer must start with '/': {path}")
    return [
        part.replace("~1", "/").replace("~0", "~")
        for part in path.split("/")[1:]
    ]


def _resolve_parent(document: Any, path: str) -> tuple[Any, str]:
    parts = _decode_pointer(path)
    if not parts:
        raise ValueError("JSON Patch operation at document root is not supported")
    current = document
    for part in parts[:-1]:
        current = _get_child(current, part, path)
    return current, parts[-1]


def _get_child(current: Any, part: str, path: str) -> Any:
    if isinstance(current, dict):
        if part not in current:
            raise ValueError(f"JSON Pointer path does not exist: {path}")
        return current[part]
    if isinstance(current, list):
        index = _list_index(part, current, path, allow_append=False)
        return current[index]
    raise ValueError(f"JSON Pointer cannot traverse non-container at: {path}")


def _list_index(part: str, current: list[Any], path: str, *, allow_append: bool) -> int:
    if allow_append and part == "-":
        return len(current)
    try:
        index = int(part)
    except ValueError as exc:
        raise ValueError(f"JSON Pointer list index must be integer at: {path}") from exc
    upper = len(current) if allow_append else len(current) - 1
    if index < 0 or index > upper:
        raise ValueError(f"JSON Pointer list index out of range at: {path}")
    return index


def _patch_add(document: Any, path: str, value: Any) -> Any:
    result = deepcopy(document)
    parent, key = _resolve_parent(result, path)
    if isinstance(parent, dict):
        parent[key] = deepcopy(value)
        return result
    if isinstance(parent, list):
        index = _list_index(key, parent, path, allow_append=True)
        parent.insert(index, deepcopy(value))
        return result
    raise ValueError(f"JSON Patch add parent is not a container at: {path}")


def _patch_replace(document: Any, path: str, value: Any) -> Any:
    result = deepcopy(document)
    parent, key = _resolve_parent(result, path)
    if isinstance(parent, dict):
        if key not in parent:
            raise ValueError(f"JSON Patch replace path does not exist: {path}")
        parent[key] = deepcopy(value)
        return result
    if isinstance(parent, list):
        index = _list_index(key, parent, path, allow_append=False)
        parent[index] = deepcopy(value)
        return result
    raise ValueError(f"JSON Patch replace parent is not a container at: {path}")


def _patch_remove(document: Any, path: str) -> Any:
    result = deepcopy(document)
    parent, key = _resolve_parent(result, path)
    if isinstance(parent, dict):
        if key not in parent:
            raise ValueError(f"JSON Patch remove path does not exist: {path}")
        del parent[key]
        return result
    if isinstance(parent, list):
        index = _list_index(key, parent, path, allow_append=False)
        del parent[index]
        return result
    raise ValueError(f"JSON Patch remove parent is not a container at: {path}")
