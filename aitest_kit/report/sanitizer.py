"""Sanitize failure text before writing test reports."""
from __future__ import annotations

import re
from pathlib import Path

SENSITIVE_PATTERN = re.compile(
    r"(authorization|password|secret|token|key=|vless://|ssh\s*端口|用户id)",
    re.IGNORECASE,
)


def sanitize_message(text: str | None, max_chars: int = 200) -> str:
    """Redact sensitive-looking messages and cap report size."""
    if not text:
        return ""
    clean = " ".join(str(text).split())
    if SENSITIVE_PATTERN.search(clean):
        return "[REDACTED]"
    if len(clean) > max_chars:
        return clean[: max_chars - 3] + "..."
    return clean


def traceback_summary(text: str | None, exception_type: str = "") -> str:
    """Return a short traceback location without absolute paths."""
    if not text:
        return exception_type

    matches = re.findall(r'File "([^"]+)", line (\d+)', text)
    if matches:
        path, line = matches[-1]
        base = Path(path).name
        return f"{base}:{line}: {exception_type}".strip(": ")

    short = sanitize_message(text, max_chars=120)
    if exception_type and exception_type not in short:
        return f"{exception_type}: {short}" if short else exception_type
    return short

