import pytest

from aitest_kit.log_assertions.rules import evaluate_request, parse_check


@pytest.mark.parametrize("source", [
    'assert reply["score"]', 'assert events.__class__',
    'assert open("file")', 'assert regex_search(expected["pattern"], "x")',
    'assert any(e for e in events for x in events)', 'assert len(events[1:])',
])
def test_rejects_unsupported_rules(source):
    with pytest.raises(ValueError):
        parse_check(source)


def test_request_keeps_rule_errors_distinct_and_continues_other_groups():
    rules = [
        {"select": {"eventType": "HIT"}, "checks": ['assert len(events) == 0', 'assert events[9]']},
        {"checks": ['assert events[9]']},
        {"checks": ['assert any(e["data"].get("ok") is True for e in events)']},
    ]
    result = evaluate_request(rules, [{"eventType": "HIT", "data": {"ok": True}}], [{}, {}, {}])
    assert result["state"] == "ERROR"
    assert [[check["state"] for check in group["checks"]] for group in result["groups"]] == [
        ["FAILED", "NOT_RUN"], ["ERROR"], ["PASSED"],
    ]


@pytest.mark.parametrize("source", [
    "assert any(len(events) for len in [0])",
    'assert regex_search("x{999999999999}", "x")',
])
def test_invalid_rules_produce_value_error(source):
    with pytest.raises(ValueError):
        parse_check(source)
