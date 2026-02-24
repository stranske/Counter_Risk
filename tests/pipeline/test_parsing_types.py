"""Tests for structured parsing/reconciliation exception types."""

from __future__ import annotations

from counter_risk.pipeline.parsing_types import UnmappedCounterpartyError


def test_unmapped_counterparty_error_exposes_required_context_attributes() -> None:
    error = UnmappedCounterpartyError(
        normalized_counterparty="Bank of America",
        raw_counterparty="Bank of America, NA",
        sheet="Total",
    )

    assert error.normalized_counterparty == "Bank of America"
    assert error.raw_counterparty == "Bank of America, NA"
    assert error.sheet == "Total"
    assert "normalized='Bank of America'" in str(error)
