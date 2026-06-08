"""Runtime assertion helpers used by generated structured assertions."""
from __future__ import annotations

from typing import Any

from jsonpath_ng import parse as parse_jsonpath


def _matches(target: Any, path: str) -> list[Any]:
    try:
        expression = parse_jsonpath(path)
    except Exception as exc:
        raise AssertionError(f"invalid JSONPath {path!r}: {exc}") from exc
    return [match.value for match in expression.find(target)]


def _format_matches(matches: list[Any]) -> str:
    preview = matches[:5]
    suffix = "" if len(matches) <= 5 else f" ... total={len(matches)}"
    return f"{preview!r}{suffix}"


def assert_jsonpath_equals(target: Any, path: str, expected: Any) -> None:
    """Assert that one JSONPath match equals expected."""
    matches = _matches(target, path)
    assert len(matches) == 1, (
        f"JSONPath {path!r} expected exactly 1 match, got {len(matches)}: "
        f"{_format_matches(matches)}"
    )
    actual = matches[0]
    assert actual == expected, (
        f"JSONPath {path!r} expected {expected!r}, got {actual!r}"
    )


def assert_jsonpath_exists(target: Any, path: str) -> None:
    """Assert that a JSONPath has at least one match."""
    matches = _matches(target, path)
    assert matches, f"JSONPath {path!r} expected at least 1 match, got 0"


def assert_jsonpath_not_exists(target: Any, path: str) -> None:
    """Assert that a JSONPath has no matches."""
    matches = _matches(target, path)
    assert not matches, (
        f"JSONPath {path!r} expected no matches, got {len(matches)}: "
        f"{_format_matches(matches)}"
    )


def assert_jsonpath_all_equals(target: Any, path: str, expected: Any) -> None:
    """Assert that every JSONPath match equals expected."""
    matches = _matches(target, path)
    assert matches, f"JSONPath {path!r} expected at least 1 match, got 0"
    failures = [
        (index, value)
        for index, value in enumerate(matches)
        if value != expected
    ]
    assert not failures, (
        f"JSONPath {path!r} expected all values to equal {expected!r}, "
        f"mismatches={failures[:5]!r}, matches={_format_matches(matches)}"
    )


def assert_jsonpath_any_equals(target: Any, path: str, expected: Any) -> None:
    """Assert that at least one JSONPath match equals expected."""
    matches = _matches(target, path)
    assert matches, f"JSONPath {path!r} expected at least 1 match, got 0"
    assert any(value == expected for value in matches), (
        f"JSONPath {path!r} expected any value to equal {expected!r}, "
        f"matches={_format_matches(matches)}"
    )


def _jsonpath_length(target: Any, path: str) -> int:
    matches = _matches(target, path)
    if len(matches) == 1 and isinstance(matches[0], (list, dict, str)):
        return len(matches[0])
    return len(matches)


def assert_jsonpath_len_equals(target: Any, path: str, expected: int) -> None:
    """Assert JSONPath result length equals expected."""
    actual = _jsonpath_length(target, path)
    assert actual == expected, (
        f"JSONPath {path!r} expected length {expected}, got {actual}"
    )


def assert_jsonpath_len_gte(target: Any, path: str, expected_min: int) -> None:
    """Assert JSONPath result length is greater than or equal to expected_min."""
    actual = _jsonpath_length(target, path)
    assert actual >= expected_min, (
        f"JSONPath {path!r} expected length >= {expected_min}, got {actual}"
    )


def assert_jsonpath_field_in_set(target: Any, path: str, values: list[Any]) -> None:
    """Assert every JSONPath match is one of the allowed values."""
    matches = _matches(target, path)
    assert matches, f"JSONPath {path!r} expected at least 1 match, got 0"
    failures = [
        (index, value)
        for index, value in enumerate(matches)
        if value not in values
    ]
    assert not failures, (
        f"JSONPath {path!r} expected all values in {values!r}, "
        f"mismatches={failures[:5]!r}, matches={_format_matches(matches)}"
    )
