"""Unit tests for series reconciliation scaffolding."""

from __future__ import annotations

from inspect import Parameter, signature

from counter_risk.pipeline.run import (
    _normalized_counterparties_from_records,
    reconcile_series_coverage,
)


def test_reconcile_series_coverage_requires_parsed_data_input_parameter() -> None:
    params = signature(reconcile_series_coverage).parameters
    parsed_data_param = params["parsed_data_by_sheet"]
    historical_headers_param = params["historical_series_headers_by_sheet"]

    assert parsed_data_param.kind is Parameter.KEYWORD_ONLY
    assert parsed_data_param.default is Parameter.empty
    assert historical_headers_param.kind is Parameter.KEYWORD_ONLY
    assert historical_headers_param.default is Parameter.empty


def test_reconcile_series_coverage_accepts_historical_headers_parameter() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={"Total": {"totals": [{"counterparty": "A"}]}},
        historical_series_headers_by_sheet={"Total": ("A", "B")},
    )

    assert result == {
        "by_sheet": {
            "Total": {
                "counterparties_in_data": ["A"],
                "normalized_counterparties_in_data": ["A"],
                "clearing_houses_in_data": [],
                "historical_series_headers": ["A", "B"],
                "normalized_historical_series_headers": ["A", "B"],
                "current_series_labels": ["A"],
                "missing_from_historical_headers": [],
                "missing_normalized_counterparties": [],
                "missing_from_data": ["B"],
                "segments_in_data": [],
                "missing_expected_segments": [],
            }
        },
        "gap_count": 1,
        "warnings": [
            "Reconciliation gap in sheet 'Total': series present in historical headers but missing from parsed data (B)"
        ],
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
        "normalized_counterparties_in_data": ["Citibank", "JPMorgan"],
        "clearing_houses_in_data": ["CME", "ICE"],
        "historical_series_headers": [],
        "normalized_historical_series_headers": [],
        "current_series_labels": ["Citibank", "CME", "ICE", "JPMorgan"],
        "missing_from_historical_headers": ["Citibank", "CME", "ICE", "JPMorgan"],
        "missing_normalized_counterparties": ["Citibank", "JPMorgan"],
        "missing_from_data": [],
        "segments_in_data": [],
        "missing_expected_segments": [],
    }
    assert result["gap_count"] == 4
    assert len(result["warnings"]) == 3
    assert result["missing_series"] == [
        {
            "sheet": "All Programs",
            "missing_from_historical_headers": ["Citibank", "CME", "ICE", "JPMorgan"],
            "data_source_context": "counterparties_and_clearing_houses",
        }
    ]
    assert any(
        "raw='Citibank'" in warning and "normalized='Citibank'" in warning
        for warning in result["warnings"]
    )
    assert any(
        "raw='JPMorgan'" in warning and "normalized='JPMorgan'" in warning
        for warning in result["warnings"]
    )


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
        "normalized_counterparties_in_data": [],
        "clearing_houses_in_data": [],
        "historical_series_headers": ["CME", "ICE"],
        "normalized_historical_series_headers": ["CME", "ICE"],
        "current_series_labels": [],
        "missing_from_historical_headers": [],
        "missing_normalized_counterparties": [],
        "missing_from_data": ["CME", "ICE"],
        "segments_in_data": [],
        "missing_expected_segments": [],
    }
    assert result["gap_count"] == 3


def test_reconcile_series_coverage_counts_each_historical_series_missing_from_data() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={"Total": {"totals": [{"counterparty": "A"}]}},
        historical_series_headers_by_sheet={"Total": ("A", "B", "C")},
    )

    assert result["by_sheet"]["Total"]["missing_from_data"] == ["B", "C"]
    assert result["gap_count"] == 2


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


def test_reconcile_series_coverage_warn_mode_includes_raw_and_normalized_counterparty() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={"Total": {"totals": [{"counterparty": "Bank of America, NA"}]}},
        historical_series_headers_by_sheet={"Total": ("Legacy Counterparty",)},
        fail_policy="warn",
    )

    assert result["gap_count"] == 2
    assert any(
        "raw='Bank of America, NA'" in warning and "normalized='Bank of America'" in warning
        for warning in result["warnings"]
    )


def test_reconcile_series_coverage_strict_mode_raises_for_unmapped_normalized_counterparty() -> (
    None
):
    try:
        reconcile_series_coverage(
            parsed_data_by_sheet={"Total": {"totals": [{"counterparty": "Bank of America, NA"}]}},
            historical_series_headers_by_sheet={"Total": ("Legacy Counterparty",)},
            fail_policy="strict",
        )
    except ValueError as exc:
        text = str(exc)
        assert "unmapped normalized counterparties" in text
        assert "Bank of America, NA" in text
        assert "Bank of America" in text
    else:
        raise AssertionError("expected strict mode reconciliation to raise")


def test_reconcile_series_coverage_does_not_warn_when_raw_labels_normalize_to_header_key() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "Total": {
                "totals": [
                    {"counterparty": "Bank of America, NA"},
                    {"counterparty": "Bank of America NA"},
                ]
            }
        },
        historical_series_headers_by_sheet={"Total": ("Bank of America",)},
    )

    assert result["gap_count"] == 1
    assert result["by_sheet"]["Total"]["missing_from_data"] == ["Bank of America"]
    assert result["by_sheet"]["Total"]["missing_normalized_counterparties"] == []
    assert not any("unmapped counterparty" in warning for warning in result["warnings"])


def test_normalized_counterparties_from_records_uses_normalization_mapping() -> None:
    totals_records = [
        {"counterparty": "Bank of America, NA"},
        {"counterparty": "Bank of America NA"},
        {"counterparty": "  Citigroup  "},
    ]

    normalized = _normalized_counterparties_from_records(totals_records)

    assert normalized == {
        "Bank of America": {"Bank of America, NA", "Bank of America NA"},
        "Citibank": {"Citigroup"},
    }


def test_normalized_counterparties_from_records_ignores_blank_counterparties() -> None:
    totals_records = [
        {"counterparty": ""},
        {"counterparty": "   "},
        {"counterparty": "JP Morgan"},
        {},
    ]

    normalized = _normalized_counterparties_from_records(totals_records)

    assert normalized == {"JP Morgan": {"JP Morgan"}}
