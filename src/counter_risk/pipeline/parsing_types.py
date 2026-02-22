"""Structured parsing/reconciliation validation error types."""

from __future__ import annotations


class ParsedDataValidationError(ValueError):
    """Base error for invalid parsed-data structures."""


class ParsedDataMissingKeyError(ParsedDataValidationError):
    """Raised when required parsed-data keys are missing."""


class ParsedDataInvalidShapeError(ParsedDataValidationError):
    """Raised when parsed-data sections have an invalid shape."""
