from __future__ import annotations


class ServiceError(ValueError):
    """A user-facing domain failure with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)
