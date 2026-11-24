import pytest

from aitest_kit.log_assertions import LogBindingError, bind_log_request, log_capture_requested
from aitest_kit.log_assertions.scope import log_request_step, use_request_recorder


class Recorder:
    def __init__(self):
        self.calls = []
        self.ids = set()

    def register(self, step, source, rules, inputs):
        self.calls.append(("register", step, source, inputs))
        return step

    def bind(self, step, value):
        if value in self.ids:
            raise ValueError("already bound")
        self.ids.add(value)
        self.calls.append(("bind", step, value))

    def freeze(self, step, inputs):
        self.calls.append(("freeze", step, inputs))

    def fail(self, step, code):
        self.calls.append(("fail", step, code))


def request_scope(expected=None):
    return log_request_step(request_step="reply", source_id="demo",
                            rules=[{"expected": expected or {}}], expected_inputs={"limit": 3})


def test_inactive_harness_and_required_recorder():
    assert not log_capture_requested()
    assert not bind_log_request("demo", "id")
    with pytest.raises(LogBindingError, match="coordinator"):
        with request_scope():
            pytest.fail("business call started without registration")


def test_register_bind_freeze_and_reject_duplicate():
    recorder = Recorder()
    with use_request_recorder(recorder):
        with request_scope({"limit": {"from_var": "limit"}, "score": {"from_response": "/a~1b/0"}}) as scope:
            assert log_capture_requested()
            assert bind_log_request("demo", "unique")
            assert bind_log_request("demo", "unique")
            scope.freeze_response({"a/b": [8]})
        with pytest.raises(LogBindingError):
            with request_scope():
                bind_log_request("demo", "unique")
    assert recorder.calls[:3] == [
        ("register", "reply", "demo", [{"limit": 3}]),
        ("bind", "reply", "unique"),
        ("freeze", "reply", [{"limit": 3, "score": 8}]),
    ]
    assert recorder.calls[-1] == ("fail", "reply", "LOG_BINDING_ERROR")
    assert not log_capture_requested()


def test_original_business_exception_survives():
    recorder = Recorder()
    with use_request_recorder(recorder), pytest.raises(RuntimeError, match="business"):
        with request_scope():
            bind_log_request("demo", "unique")
            raise RuntimeError("business")
    assert recorder.calls[-1] == ("freeze", "reply", [{}])


def test_nested_credentials_do_not_reach_recorder():
    from aitest_kit.log_assertions.values import LogInputError

    recorder = Recorder()
    with use_request_recorder(recorder), pytest.raises(LogInputError, match="sensitive"):
        with request_scope({"data": {"from_response": "/result"}}) as scope:
            bind_log_request("demo", "unique")
            scope.freeze_response({"result": {"items": [{"access_token": "fixture-value"}]}})
    assert recorder.calls[-1] == ("fail", "reply", "LOG_INPUT_ERROR")


def test_selects_before_copying_other_response_fields():
    recorder = Recorder()
    with use_request_recorder(recorder), request_scope({"count": {"from_response": "/usage/total_tokens"}}) as scope:
        bind_log_request("demo", "unique")
        scope.freeze_response({"usage": {"total_tokens": 25}, "unused": object()})
    assert recorder.calls[-1] == ("freeze", "reply", [{"count": 25}])



def test_log_platform_token_env_cannot_be_frozen_by_profile():
    from aitest_kit.codegen.log_assertion_validation import validate_expected_variables

    flow = {"log_assertions": [{"expected": {"value": {"from_var": "business_value"}}}]}
    variables = {"defaults": {"business_value": {"env": "AITEST_LOG_TOKEN"}}}
    assert validate_expected_variables(flow, "case_flows.TC-DEMO-001", variables)[0][0] == "E535"
