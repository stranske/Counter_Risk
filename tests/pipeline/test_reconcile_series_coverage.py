"""Unit tests for series reconciliation scaffolding."""

from __future__ import annotations

from counter_risk.pipeline.run import reconcile_series_coverage


def test_reconcile_series_coverage_accepts_historical_headers_parameter() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={"Total": {"totals": [{"counterparty": "A"}]}},
        historical_series_headers_by_sheet={"Total": ("A", "B")},
    )

    assert result == {"by_sheet": {}, "gap_count": 0, "warnings": []}
