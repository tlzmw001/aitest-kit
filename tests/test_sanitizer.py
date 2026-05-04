from aitest_kit.report.sanitizer import sanitize_message, traceback_summary


def test_sanitize_message_redacts_sensitive_text():
    assert sanitize_message("Authorization: Bearer abc") == "[REDACTED]"
    assert sanitize_message("password=secret") == "[REDACTED]"


def test_sanitize_message_truncates_long_text():
    text = "x" * 250
    clean = sanitize_message(text)
    assert len(clean) == 200
    assert clean.endswith("...")


def test_traceback_summary_drops_absolute_path():
    tb = 'File "/Users/example/project/test_demo.py", line 42, in test_case\nAssertionError'
    assert traceback_summary(tb, "AssertionError") == "test_demo.py:42: AssertionError"

