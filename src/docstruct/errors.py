"""Typed exceptions for docstruct."""

from __future__ import annotations


class DocstructError(Exception):
    """Base exception for all docstruct errors."""


class ProviderError(DocstructError):
    """Raised when a provider fails to extract or returns unusable data."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        status_code: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.__cause__ = cause


class ValidationError(DocstructError):
    """Raised when schema or business-rule validation fails after retries."""

    def __init__(
        self,
        message: str,
        *,
        errors: list[str] | None = None,
        attempts: int = 0,
    ) -> None:
        super().__init__(message)
        self.errors = errors or []
        self.attempts = attempts


class SchemaError(DocstructError):
    """Raised when a provided schema is invalid or cannot be normalized."""


class SerializationError(DocstructError):
    """Raised when JSON/XML serialization or XSD validation fails."""
