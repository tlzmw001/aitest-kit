"""Rule-based failure classification for test reports."""
from __future__ import annotations

ENVIRONMENT_EXCEPTIONS = {
    "ConnectionError",
    "ConnectionRefusedError",
    "ConnectError",
    "TimeoutError",
    "ReadTimeout",
    "ConnectTimeout",
    "OSError",
}

CODEGEN_EXCEPTIONS = {
    "NameError",
    "TypeError",
    "AttributeError",
    "SyntaxError",
}


def classify_failure(phase: str, exception_type: str) -> str:
    """Classify a failure using the Phase 3 MVP rules."""
    phase = (phase or "unknown").lower()
    exception_type = exception_type or ""

    if phase == "teardown":
        return "TEARDOWN_ERROR"
    if phase == "setup":
        if exception_type in ENVIRONMENT_EXCEPTIONS:
            return "ENVIRONMENT_ERROR"
        return "FIXTURE_ERROR"
    if phase == "call":
        if exception_type == "AssertionError":
            return "ASSERTION_FAILURE"
        if exception_type in CODEGEN_EXCEPTIONS:
            return "CODEGEN_ERROR"
        return "UNKNOWN"
    return "UNKNOWN"

