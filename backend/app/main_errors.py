"""Shared API error type (separate module to avoid circular imports)."""
from __future__ import annotations


class ApiError(Exception):
    """Error with a stable code, rendered as clean JSON by the app's handler."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code, self.code, self.message = status_code, code, message
