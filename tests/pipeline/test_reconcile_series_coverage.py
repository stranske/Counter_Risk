"""Unit tests for series reconciliation scaffolding."""

from __future__ import annotations

from counter_risk.pipeline.run import reconcile_series_coverage


def test_reconcile_series_coverage_accepts_historical_headers_parameter() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={"Total": {"totals": [{"counterparty": "A"}]}},
        historical_series_headers_by_sheet={"Total": ("A", "B")},
    )

    assert result == {
        "by_sheet": {
            "Total": {
                "counterparties_in_data": ["A"],
                "clearing_houses_in_data": [],
                "current_series_labels": ["A"],
            }
        },
        "gap_count": 0,
        "warnings": [],
    }


def test_reconcile_series_coverage_extracts_counterparties_and_clearing_houses() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "All Programs": {
                "totals": [
                    {"counterparty": "Citibank"},
                    {"counterparty": "  JPMorgan  "},
                    {"counterparty": ""},
                    {"counterparty": "Citibank"},
                ],
                "futures": [
                    {"clearing_house": "CME"},
                    {"clearing_house": "  ICE  "},
                    {"clearing_house": ""},
                    {"clearing_house": "CME"},
                ],
            }
        },
        historical_series_headers_by_sheet={},
    )

    assert result["by_sheet"]["All Programs"] == {
        "counterparties_in_data": ["Citibank", "JPMorgan"],
        "clearing_houses_in_data": ["CME", "ICE"],
        "current_series_labels": ["CME", "Citibank", "ICE", "JPMorgan"],
    }
