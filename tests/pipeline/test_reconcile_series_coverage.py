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
                "historical_series_headers": ["A", "B"],
                "current_series_labels": ["A"],
                "missing_from_historical_headers": [],
                "missing_from_data": ["B"],
                "segments_in_data": [],
                "missing_expected_segments": [],
            }
        },
        "gap_count": 0,
        "warnings": [],
        "missing_series": [],
        "missing_segments": [],
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
        "historical_series_headers": [],
        "current_series_labels": ["CME", "Citibank", "ICE", "JPMorgan"],
        "missing_from_historical_headers": ["Citibank", "CME", "ICE", "JPMorgan"],
        "missing_from_data": [],
        "segments_in_data": [],
        "missing_expected_segments": [],
    }
    assert result["gap_count"] == 4
    assert len(result["warnings"]) == 1
    assert result["missing_series"] == [
        {
            "sheet": "All Programs",
            "missing_from_historical_headers": ["Citibank", "CME", "ICE", "JPMorgan"],
            "data_source_context": "counterparties_and_clearing_houses",
        }
    ]


def test_reconcile_series_coverage_extracts_historical_series_headers_per_sheet() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={"Total": {"totals": [{"counterparty": "A"}]}},
        historical_series_headers_by_sheet={
            "Total": ("  B  ", "A", "", "A"),
            "Futures": ("  ICE  ", "CME", "CME"),
        },
    )

    assert result["by_sheet"]["Total"]["historical_series_headers"] == ["A", "B"]
    assert result["by_sheet"]["Futures"] == {
        "counterparties_in_data": [],
        "clearing_houses_in_data": [],
        "historical_series_headers": ["CME", "ICE"],
        "current_series_labels": [],
        "missing_from_historical_headers": [],
        "missing_from_data": ["CME", "ICE"],
        "segments_in_data": [],
        "missing_expected_segments": [],
    }


def test_reconcile_series_coverage_reports_missing_expected_segments_by_variant() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "CPRS - CH": {
                "futures": [
                    {"clearing_house": "CME", "segment": "swaps"},
                    {"clearing_house": "ICE", "segment": "repo"},
                ]
            }
        },
        historical_series_headers_by_sheet={"CPRS - CH": ("CME", "ICE")},
        variant="all_programs",
        expected_segments_by_variant={
            "all_programs": ("swaps", "repo", "futures_cdx"),
            "ex_trend": ("swaps", "repo"),
        },
    )

    assert result["by_sheet"]["CPRS - CH"]["segments_in_data"] == ["repo", "swaps"]
    assert result["by_sheet"]["CPRS - CH"]["missing_expected_segments"] == ["futures_cdx"]
    assert result["gap_count"] == 1
    assert result["missing_segments"] == [
        {
            "variant": "all_programs",
            "sheet": "CPRS - CH",
            "expected_segment_identifiers": ["futures_cdx"],
        }
    ]
    assert "expected segments missing from parsed results (futures_cdx)" in result["warnings"][0]
