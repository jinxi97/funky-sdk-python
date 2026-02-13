"""Custom exception types for funky SDK."""

from __future__ import annotations

from typing import Any


class FunkyError(Exception):
    """Base exception type for SDK errors."""


class ConfigurationError(FunkyError):
    """Raised when SDK configuration is invalid or incomplete."""


class APIError(FunkyError):
    """Raised when the backend API returns a failure response."""

    def __init__(self, status_code: int, message: str, details: Any | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details
