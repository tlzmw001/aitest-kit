"""Runtime case identity context for generated tests."""
from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CaseContext:
    case_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


_CURRENT_CASE_CONTEXT: ContextVar[CaseContext | None] = ContextVar(
    "aitest_current_case_context",
    default=None,
)


def current_case_id() -> str | None:
    """Return the current generated test case id, or None outside a test body."""
    context = _CURRENT_CASE_CONTEXT.get()
    return context.case_id if context is not None else None


def set_case_context(
    case_id: str,
    metadata: dict[str, Any] | None = None,
) -> Token[CaseContext | None]:
    """Set current generated test case identity and return a reset token."""
    return _CURRENT_CASE_CONTEXT.set(
        CaseContext(case_id=str(case_id), metadata=dict(metadata or {}))
    )


def reset_case_context(token: Token[CaseContext | None]) -> None:
    """Reset current generated test case identity."""
    _CURRENT_CASE_CONTEXT.reset(token)
