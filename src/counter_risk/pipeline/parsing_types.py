"""Structured parsing/reconciliation validation error types.

Exception API contract
- ``UnmappedCounterpartyError`` is raised for unmapped reconciliation counterparties.
- ``UnmappedCounterpartyError.normalized_counterparty`` is a ``str`` and stores the
  exact normalized counterparty value that triggered the error.
- ``UnmappedCounterpartyError.raw_counterparty`` is a ``str`` and stores the exact
  original parsed counterparty value that triggered the error.
- ``UnmappedCounterpartyError.sheet`` is ``str | None`` and stores optional worksheet
  context for the mismatch.
"""

from __future__ import annotations

from counter_risk.pipeline.errors import UnmappedCounterpartyError


class ParsedDataValidationError(ValueError):
    """Base error for invalid parsed-data structures."""


class ParsedDataMissingKeyError(ParsedDataValidationError):
    """Raised when required parsed-data keys are missing."""


class ParsedDataInvalidShapeError(ParsedDataValidationError):
    """Raised when parsed-data sections have an invalid shape."""
