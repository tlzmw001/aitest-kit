from __future__ import annotations


class ConsoleError(Exception):
    """Stable API error raised by the local console boundary."""

    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
