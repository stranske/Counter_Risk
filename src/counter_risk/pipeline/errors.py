"""Structured pipeline/reconciliation exception types."""

from __future__ import annotations


class UnmappedCounterpartyError(ValueError):
    """Raised when reconciliation cannot map a parsed counterparty to historical series.

    Contract:
        This exception exposes machine-readable context fields as direct attributes.
        ``normalized_counterparty`` and ``raw_counterparty`` are always populated with
        the exact triggering values.

    Attributes:
        normalized_counterparty (str): Deterministic normalized counterparty label.
        raw_counterparty (str): Original parsed counterparty label before normalization.
        sheet (str | None): Optional worksheet context where the mismatch occurred.
    """

    normalized_counterparty: str
    raw_counterparty: str
    sheet: str | None

    def __init__(
        self, *, normalized_counterparty: str, raw_counterparty: str, sheet: str | None = None
    ) -> None:
        self.normalized_counterparty = normalized_counterparty
        self.raw_counterparty = raw_counterparty
        self.sheet = sheet
        message = (
            "Unmapped normalized counterparty: "
            f"raw={raw_counterparty!r}, normalized={normalized_counterparty!r}"
        )
        if sheet:
            message = f"{message} in sheet {sheet!r}"
        super().__init__(message)
