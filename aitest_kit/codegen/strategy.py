"""Shared case strategy resolution for codegen planning and validation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


STRATEGY_SKIPPED = "skipped"
STRATEGY_CUSTOM_CASE_BODY = "custom_case_body"
STRATEGY_STRUCTURED_CASE_FLOW = "structured_case_flow"
STRATEGY_MANUAL = "manual"
STRATEGY_DEFAULT_HTTP = "default_http"

PROFILE_INTENT_NONE = "none"


@dataclass(frozen=True)
class StrategyResolution:
    """Resolved strategy plus profile-declared executable intent for one case."""

    case_id: str
    final_strategy: str
    final_source: str
    final_reason: str
    profile_intent: str
    profile_source: str
    manual: bool
    skipped: bool
    skip_reason: str | None


def has_marker(markers: Sequence[str], text: str) -> bool:
    """Return whether any Markdown marker contains text, case-insensitively."""
    needle = text.lower()
    return any(needle in marker.lower() for marker in markers)


def skip_reason_from_markers(markers: Sequence[str]) -> str | None:
    """Return the first feasibility-suspect marker that makes a case skipped."""
    for marker in markers:
        if has_marker([marker], "可行性存疑"):
            return marker
    return None


def resolve_case_strategy(
    *,
    case_id: str,
    markers: Sequence[str],
    case_bodies: Mapping[str, Any],
    case_flows: Mapping[str, Any],
) -> StrategyResolution:
    """Resolve final generation strategy and profile intent for one case."""
    profile_intent = PROFILE_INTENT_NONE
    profile_source = ""
    if case_id in case_bodies:
        profile_intent = STRATEGY_CUSTOM_CASE_BODY
        profile_source = f"profile.case_bodies.{case_id}"
    elif case_id in case_flows:
        profile_intent = STRATEGY_STRUCTURED_CASE_FLOW
        profile_source = f"profile.case_flows.{case_id}"

    skip_reason = skip_reason_from_markers(markers)
    manual = has_marker(markers, "manual")
    if skip_reason:
        return StrategyResolution(
            case_id=case_id,
            final_strategy=STRATEGY_SKIPPED,
            final_source="markers",
            final_reason=skip_reason,
            profile_intent=profile_intent,
            profile_source=profile_source,
            manual=manual,
            skipped=True,
            skip_reason=skip_reason,
        )
    if case_id in case_bodies:
        return StrategyResolution(
            case_id=case_id,
            final_strategy=STRATEGY_CUSTOM_CASE_BODY,
            final_source=f"profile.case_bodies.{case_id}",
            final_reason="profile provides custom body",
            profile_intent=profile_intent,
            profile_source=profile_source,
            manual=manual,
            skipped=False,
            skip_reason=None,
        )
    if case_id in case_flows:
        return StrategyResolution(
            case_id=case_id,
            final_strategy=STRATEGY_STRUCTURED_CASE_FLOW,
            final_source=f"profile.case_flows.{case_id}",
            final_reason="profile provides structured flow",
            profile_intent=profile_intent,
            profile_source=profile_source,
            manual=manual,
            skipped=False,
            skip_reason=None,
        )
    if manual:
        return StrategyResolution(
            case_id=case_id,
            final_strategy=STRATEGY_MANUAL,
            final_source="markers",
            final_reason="manual marker",
            profile_intent=profile_intent,
            profile_source=profile_source,
            manual=True,
            skipped=False,
            skip_reason=None,
        )
    return StrategyResolution(
        case_id=case_id,
        final_strategy=STRATEGY_DEFAULT_HTTP,
        final_source="default",
        final_reason="no custom strategy",
        profile_intent=profile_intent,
        profile_source=profile_source,
        manual=False,
        skipped=False,
        skip_reason=None,
    )
