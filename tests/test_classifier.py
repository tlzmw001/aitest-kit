from aitest_kit.report.classifier import classify_failure


def test_classifies_environment_setup_errors():
    assert classify_failure("setup", "ConnectionRefusedError") == "ENVIRONMENT_ERROR"
    assert classify_failure("setup", "ConnectError") == "ENVIRONMENT_ERROR"


def test_classifies_fixture_setup_errors():
    assert classify_failure("setup", "ValueError") == "TEST_SCAFFOLD_ERROR"


def test_classifies_profile_variable_errors_as_precondition_missing():
    assert classify_failure("call", "ProfileVariableError") == "PRECONDITION_MISSING"
    assert classify_failure("setup", "ProfileVariableError") == "PRECONDITION_MISSING"
    assert classify_failure("setup", "PreconditionMissing") == "PRECONDITION_MISSING"


def test_classifies_codegen_and_assertion_errors():
    assert classify_failure("call", "NameError") == "CODEGEN_ERROR"
    assert classify_failure("call", "AssertionError") == "ASSERTION_FAILURE"


def test_classifies_teardown_and_unknown():
    assert classify_failure("teardown", "ValueError") == "TEARDOWN_ERROR"
    assert classify_failure("call", "ValueError") == "UNKNOWN"
