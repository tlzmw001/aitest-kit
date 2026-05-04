from aitest_kit.report.classifier import classify_failure


def test_classifies_environment_setup_errors():
    assert classify_failure("setup", "ConnectionRefusedError") == "ENVIRONMENT_ERROR"
    assert classify_failure("setup", "ConnectError") == "ENVIRONMENT_ERROR"


def test_classifies_fixture_setup_errors():
    assert classify_failure("setup", "ValueError") == "FIXTURE_ERROR"


def test_classifies_codegen_and_assertion_errors():
    assert classify_failure("call", "NameError") == "CODEGEN_ERROR"
    assert classify_failure("call", "AssertionError") == "ASSERTION_FAILURE"


def test_classifies_teardown_and_unknown():
    assert classify_failure("teardown", "ValueError") == "TEARDOWN_ERROR"
    assert classify_failure("call", "ValueError") == "UNKNOWN"

