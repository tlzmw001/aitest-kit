from __future__ import annotations

from aitest_kit.codegen.strategy import (
    PROFILE_INTENT_NONE,
    STRATEGY_CUSTOM_CASE_BODY,
    STRATEGY_DEFAULT_HTTP,
    STRATEGY_MANUAL,
    STRATEGY_SKIPPED,
    STRATEGY_STRUCTURED_CASE_FLOW,
    resolve_case_strategy,
)


def test_strategy_resolution_preserves_final_priority_over_profile_intent():
    resolution = resolve_case_strategy(
        case_id="TC-DEMO-001",
        markers=["[!可行性存疑: service unavailable]"],
        case_bodies={},
        case_flows={"TC-DEMO-001": {"steps": []}},
    )

    assert resolution.final_strategy == STRATEGY_SKIPPED
    assert resolution.final_source == "markers"
    assert resolution.profile_intent == STRATEGY_STRUCTURED_CASE_FLOW
    assert resolution.profile_source == "profile.case_flows.TC-DEMO-001"
    assert resolution.skipped is True
    assert resolution.skip_reason == "[!可行性存疑: service unavailable]"


def test_strategy_resolution_profile_body_wins_over_flow_and_manual():
    resolution = resolve_case_strategy(
        case_id="TC-DEMO-001",
        markers=["[manual]"],
        case_bodies={"TC-DEMO-001": ["assert True"]},
        case_flows={"TC-DEMO-001": {"steps": []}},
    )

    assert resolution.final_strategy == STRATEGY_CUSTOM_CASE_BODY
    assert resolution.final_source == "profile.case_bodies.TC-DEMO-001"
    assert resolution.final_reason == "profile provides custom body"
    assert resolution.profile_intent == STRATEGY_CUSTOM_CASE_BODY
    assert resolution.manual is True


def test_strategy_resolution_flow_wins_over_manual():
    resolution = resolve_case_strategy(
        case_id="TC-DEMO-001",
        markers=["[manual]"],
        case_bodies={},
        case_flows={"TC-DEMO-001": {"steps": []}},
    )

    assert resolution.final_strategy == STRATEGY_STRUCTURED_CASE_FLOW
    assert resolution.final_source == "profile.case_flows.TC-DEMO-001"
    assert resolution.final_reason == "profile provides structured flow"
    assert resolution.profile_intent == STRATEGY_STRUCTURED_CASE_FLOW
    assert resolution.manual is True


def test_strategy_resolution_manual_and_default_without_profile_intent():
    manual = resolve_case_strategy(
        case_id="TC-DEMO-001",
        markers=["[manual]"],
        case_bodies={},
        case_flows={},
    )
    default = resolve_case_strategy(
        case_id="TC-DEMO-002",
        markers=[],
        case_bodies={},
        case_flows={},
    )

    assert manual.final_strategy == STRATEGY_MANUAL
    assert manual.profile_intent == PROFILE_INTENT_NONE
    assert default.final_strategy == STRATEGY_DEFAULT_HTTP
    assert default.final_source == "default"
    assert default.profile_intent == PROFILE_INTENT_NONE
