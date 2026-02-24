"""Unit tests for series reconciliation scaffolding."""

from __future__ import annotations

from inspect import Parameter, signature

import pytest

from counter_risk.pipeline.parsing_types import (
    ParsedDataInvalidShapeError,
    ParsedDataMissingKeyError,
    UnmappedCounterpartyError,
)
from counter_risk.pipeline.run import (
    _normalized_counterparties_from_parsed_data,
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
        parsed_data_by_sheet={"Total": {"totals": [{"counterparty": "A"}], "futures": []}},
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
                "canonical_key_by_series": {"A": "A"},
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
        "canonical_key_by_series": {
            "Citibank": "Citibank",
            "JPMorgan": "JPMorgan",
            "CME": "CME",
            "ICE": "ICE",
        },
    }
    assert result["gap_count"] == 4
    assert len(result["warnings"]) == 3
    assert {
        "sheet": "All Programs",
        "missing_from_historical_headers": ["Citibank", "CME", "ICE", "JPMorgan"],
        "data_source_context": "counterparties_and_clearing_houses",
    } in result["missing_series"]
    assert any(
        entry.get("error_type") == "unmapped_counterparty"
        and set(entry.get("raw_counterparties", [])) == {"Citibank", "  JPMorgan  "}
        for entry in result["missing_series"]
    )
    assert any(
        "raw='Citibank'" in warning and "normalized='Citibank'" in warning
        for warning in result["warnings"]
    )
    assert any(
        "normalized='JPMorgan'" in warning and "JPMorgan" in warning
        for warning in result["warnings"]
    )


def test_reconcile_series_coverage_extracts_historical_series_headers_per_sheet() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={"Total": {"totals": [{"counterparty": "A"}], "futures": []}},
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
        "canonical_key_by_series": {},
    }
    assert result["gap_count"] == 3


def test_reconcile_series_coverage_counts_each_historical_series_missing_from_data() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={"Total": {"totals": [{"counterparty": "A"}], "futures": []}},
        historical_series_headers_by_sheet={"Total": ("A", "B", "C")},
    )

    assert result["by_sheet"]["Total"]["missing_from_data"] == ["B", "C"]
    assert result["gap_count"] == 2


def test_reconcile_series_coverage_counts_missing_historical_series_with_no_other_gaps() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={"SheetA": {"totals": [{"counterparty": "A"}], "futures": []}},
        historical_series_headers_by_sheet={"SheetA": ("A", "B")},
    )

    assert result["by_sheet"]["SheetA"]["missing_from_data"] == ["B"]
    assert result["by_sheet"]["SheetA"]["missing_expected_segments"] == []
    assert result["gap_count"] == 1


def test_reconcile_series_coverage_counts_missing_historical_series_exactly_per_sheet() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "SheetA": {"totals": [{"counterparty": "A"}], "futures": []},
            "SheetB": {"totals": [{"counterparty": "X"}, {"counterparty": "Y"}], "futures": []},
        },
        historical_series_headers_by_sheet={
            "SheetA": ("A", "B", "C"),
            "SheetB": ("X", "Y"),
        },
    )

    assert result["by_sheet"]["SheetA"]["missing_from_data"] == ["B", "C"]
    assert result["by_sheet"]["SheetB"]["missing_from_data"] == []
    assert result["gap_count"] == 2


def test_reconcile_series_coverage_reports_missing_expected_segments_by_variant() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "CPRS - CH": {
                "totals": [],
                "futures": [
                    {"clearing_house": "CME", "segment": "swaps"},
                    {"clearing_house": "ICE", "segment": "repo"},
                ],
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
        parsed_data_by_sheet={
            "Total": {"totals": [{"counterparty": "Bank of America, NA"}], "futures": []}
        },
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
    with pytest.raises(UnmappedCounterpartyError) as exc_info:
        reconcile_series_coverage(
            parsed_data_by_sheet={
                "Total": {"totals": [{"counterparty": "Bank of America, NA"}], "futures": []}
            },
            historical_series_headers_by_sheet={"Total": ("Legacy Counterparty",)},
            fail_policy="strict",
        )

    error = exc_info.value
    assert error.normalized_counterparty == "Bank of America"
    assert error.raw_counterparty == "Bank of America, NA"
    assert error.sheet == "Total"


def test_strict_unmapped_counterparty_raises_with_raw_value() -> None:
    raw_value = " ACME  LTD "
    with pytest.raises(Exception) as exc_info:
        reconcile_series_coverage(
            parsed_data_by_sheet={
                "Total": {"totals": [{"counterparty": raw_value}], "futures": []}
            },
            historical_series_headers_by_sheet={"Total": ("Legacy Counterparty",)},
            fail_policy="strict",
        )

    assert isinstance(exc_info.value, UnmappedCounterpartyError)
    assert exc_info.value.raw_counterparty == raw_value


def test_strict_unmapped_counterparty_exception_contains_normalized_value() -> None:
    raw_value = " ACME  LTD "
    with pytest.raises(Exception) as exc_info:
        reconcile_series_coverage(
            parsed_data_by_sheet={
                "Total": {"totals": [{"counterparty": raw_value}], "futures": []}
            },
            historical_series_headers_by_sheet={"Total": ("Legacy Counterparty",)},
            fail_policy="strict",
        )

    error = exc_info.value
    assert isinstance(error, UnmappedCounterpartyError)
    if hasattr(error, "normalized_counterparty"):
        assert error.normalized_counterparty == "ACME LTD"
        assert error.normalized_counterparty != error.raw_counterparty
    elif hasattr(error, "normalized_value"):
        normalized_value = getattr(error, "normalized_value")
        assert normalized_value == "ACME LTD"
        assert normalized_value != error.raw_counterparty
    else:
        assert not hasattr(error, "normalized_counterparty")
        assert not hasattr(error, "normalized_value")


def test_reconcile_series_coverage_warn_mode_records_structured_exception_without_raising() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "Total": {"totals": [{"counterparty": "Bank of America, NA"}], "futures": []}
        },
        historical_series_headers_by_sheet={"Total": ("Legacy Counterparty",)},
        fail_policy="warn",
    )

    exceptions = result.get("exceptions")
    assert isinstance(exceptions, list)
    assert len(exceptions) == 1
    assert isinstance(exceptions[0], UnmappedCounterpartyError)
    assert exceptions[0].normalized_counterparty == "Bank of America"
    assert exceptions[0].raw_counterparty == "Bank of America, NA"


def test_non_strict_unmapped_counterparty_sets_missing_series() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "Total": {"totals": [{"counterparty": " ACME  LTD "}], "futures": []}
        },
        historical_series_headers_by_sheet={"Total": ("Legacy Counterparty",)},
        fail_policy="warn",
    )

    assert "missing_series" in result
    assert len(result["missing_series"]) >= 1


def test_non_strict_missing_series_contains_mapping_metadata() -> None:
    raw_value = " ACME  LTD "
    result = reconcile_series_coverage(
        parsed_data_by_sheet={"Total": {"totals": [{"counterparty": raw_value}], "futures": []}},
        historical_series_headers_by_sheet={"Total": ("Legacy Counterparty",)},
        fail_policy="warn",
    )

    assert any(
        entry.get("error_type") == "unmapped_counterparty"
        and raw_value in entry.get("raw_counterparties", [])
        for entry in result["missing_series"]
    )


def test_reconcile_series_coverage_does_not_warn_when_raw_labels_normalize_to_header_key() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "Total": {
                "totals": [
                    {"counterparty": "Bank of America, NA"},
                    {"counterparty": "Bank of America NA"},
                ],
                "futures": [],
            }
        },
        historical_series_headers_by_sheet={"Total": ("Bank of America",)},
    )

    assert result["gap_count"] == 0
    assert result["by_sheet"]["Total"]["missing_from_data"] == []
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


def test_normalized_counterparties_from_parsed_data_uses_totals_records() -> None:
    parsed_sections = {
        "totals": [
            {"counterparty": "Bank of America, NA"},
            {"counterparty": "Bank of America NA"},
            {"counterparty": "  Citigroup  "},
            {"counterparty": "   "},
            {},
        ],
        "futures": [{"clearing_house": "CME"}],
    }

    normalized = _normalized_counterparties_from_parsed_data(parsed_sections)

    assert normalized == {
        "Bank of America": {"Bank of America, NA", "Bank of America NA"},
        "Citibank": {"Citigroup"},
    }


def test_normalized_counterparties_from_parsed_data_handles_missing_totals_key() -> None:
    normalized = _normalized_counterparties_from_parsed_data(
        {"futures": [{"clearing_house": "ICE"}]}
    )

    assert normalized == {}


def test_reconcile_series_coverage_fails_fast_when_required_sections_missing() -> None:
    with pytest.raises(ParsedDataMissingKeyError, match="Missing required parsed_data section"):
        reconcile_series_coverage(
            parsed_data_by_sheet={"Total": {"totals": [{"counterparty": "A"}]}},
            historical_series_headers_by_sheet={"Total": ("A",)},
        )


def test_reconcile_series_coverage_fails_fast_when_section_shape_is_invalid() -> None:
    with pytest.raises(ParsedDataInvalidShapeError, match="Invalid parsed_data shape"):
        reconcile_series_coverage(
            parsed_data_by_sheet={"Total": {"totals": {"counterparty": "A"}, "futures": []}},
            historical_series_headers_by_sheet={"Total": ("A",)},
        )


def test_reconcile_series_coverage_accepts_list_of_mapping_sections() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "Total": {
                "totals": [{"counterparty": "A", "Notional": 1.0}],
                "futures": [{"clearing_house": "ICE", "notional": 1.0}],
            }
        },
        historical_series_headers_by_sheet={"Total": ("A", "ICE")},
    )

    assert result["gap_count"] == 0


# ---------------------------------------------------------------------------
# Tricky canonicalization cases: spaces, punctuation, special chars
# ---------------------------------------------------------------------------


def test_reconcile_historical_header_extra_spaces_still_matches() -> None:
    """Historical headers with extra leading/trailing spaces should match after canonicalization."""
    result = reconcile_series_coverage(
        parsed_data_by_sheet={"Total": {"totals": [{"counterparty": "JPMorgan"}], "futures": []}},
        historical_series_headers_by_sheet={"Total": ("  JPMorgan  ",)},
    )

    assert result["gap_count"] == 0
    assert result["by_sheet"]["Total"]["missing_from_data"] == []
    assert result["by_sheet"]["Total"]["historical_series_headers"] == ["JPMorgan"]


def test_reconcile_historical_header_internal_spaces_collapsed() -> None:
    """Historical headers with repeated internal spaces are collapsed before matching."""
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "Total": {"totals": [{"counterparty": "Bank of America"}], "futures": []}
        },
        historical_series_headers_by_sheet={"Total": ("Bank  of  America",)},
    )

    assert result["gap_count"] == 0
    assert result["by_sheet"]["Total"]["historical_series_headers"] == ["Bank of America"]


def test_reconcile_historical_header_endash_canonicalized() -> None:
    """En-dash in historical headers is normalized to hyphen-minus before matching."""
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "Total": {
                "totals": [{"counterparty": "Korea Exchange-Seoul"}],
                "futures": [],
            }
        },
        # Historical header uses en-dash (U+2013)
        historical_series_headers_by_sheet={"Total": ("Korea Exchange\u2013Seoul",)},
    )

    assert result["gap_count"] == 0
    assert result["by_sheet"]["Total"]["historical_series_headers"] == ["Korea Exchange-Seoul"]
    assert result["by_sheet"]["Total"]["missing_from_data"] == []


def test_reconcile_historical_header_emdash_canonicalized() -> None:
    """Em-dash in historical headers is normalized to hyphen-minus before matching."""
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "Total": {
                "totals": [{"counterparty": "Korea Exchange-Seoul"}],
                "futures": [],
            }
        },
        # Historical header uses em-dash (U+2014)
        historical_series_headers_by_sheet={"Total": ("Korea Exchange\u2014Seoul",)},
    )

    assert result["gap_count"] == 0
    assert result["by_sheet"]["Total"]["historical_series_headers"] == ["Korea Exchange-Seoul"]


def test_reconcile_counterparty_curly_apostrophe_matches_historical() -> None:
    """Curly apostrophe in parsed counterparty normalizes to match historical header."""
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "Total": {
                # Goldman Sachs Int'l with curly right-apostrophe (U+2019)
                "totals": [{"counterparty": "Goldman Sachs Int\u2019l"}],
                "futures": [],
            }
        },
        historical_series_headers_by_sheet={"Total": ("Goldman Sachs",)},
    )

    assert result["gap_count"] == 0
    assert result["by_sheet"]["Total"]["missing_normalized_counterparties"] == []


def test_reconcile_series_coverage_canonical_key_by_series_maps_raw_to_canonical() -> None:
    """canonical_key_by_series maps each raw series label to its canonical matching key."""
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "Total": {
                "totals": [{"counterparty": "Bank of America, NA"}],
                "futures": [{"clearing_house": "CME"}],
            }
        },
        historical_series_headers_by_sheet={"Total": ("Bank of America", "CME")},
    )

    assert result["by_sheet"]["Total"]["canonical_key_by_series"] == {
        "Bank of America, NA": "Bank of America",
        "CME": "CME",
    }
    assert result["gap_count"] == 0


def test_reconcile_series_coverage_canonical_key_by_series_multiple_raw_forms() -> None:
    """canonical_key_by_series captures all raw forms that map to the same canonical key."""
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "Total": {
                "totals": [
                    {"counterparty": "Bank of America, NA"},
                    {"counterparty": "Bank of America NA"},
                ],
                "futures": [],
            }
        },
        historical_series_headers_by_sheet={"Total": ("Bank of America",)},
    )

    assert result["by_sheet"]["Total"]["canonical_key_by_series"] == {
        "Bank of America, NA": "Bank of America",
        "Bank of America NA": "Bank of America",
    }
    assert result["gap_count"] == 0


def test_reconcile_series_coverage_canonical_key_by_series_empty_when_no_data() -> None:
    """canonical_key_by_series is empty when there are no series in parsed data."""
    result = reconcile_series_coverage(
        parsed_data_by_sheet={"Total": {"totals": [], "futures": []}},
        historical_series_headers_by_sheet={"Total": ("JPMorgan",)},
    )

    assert result["by_sheet"]["Total"]["canonical_key_by_series"] == {}


# ---------------------------------------------------------------------------
# Clearing house canonicalization in lookup/match operations
# ---------------------------------------------------------------------------


def test_reconcile_clearing_house_extra_spaces_still_matches_historical() -> None:
    """Clearing house with leading/trailing spaces in parsed data matches canonical historical header."""
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "Futures": {"totals": [], "futures": [{"clearing_house": "  CME  "}]}
        },
        historical_series_headers_by_sheet={"Futures": ("CME",)},
    )

    assert result["gap_count"] == 0
    assert result["by_sheet"]["Futures"]["clearing_houses_in_data"] == ["CME"]
    assert result["by_sheet"]["Futures"]["missing_from_data"] == []


def test_reconcile_clearing_house_internal_spaces_collapsed_before_match() -> None:
    """Clearing house with repeated internal spaces is collapsed before matching historical header."""
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "Futures": {"totals": [], "futures": [{"clearing_house": "ICE  Clear"}]}
        },
        historical_series_headers_by_sheet={"Futures": ("ICE Clear",)},
    )

    assert result["gap_count"] == 0
    assert result["by_sheet"]["Futures"]["clearing_houses_in_data"] == ["ICE Clear"]
    assert result["by_sheet"]["Futures"]["missing_from_data"] == []


def test_reconcile_clearing_house_endash_canonicalized_before_match() -> None:
    """En-dash in clearing house name from parsed data is normalized before matching historical header."""
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "Futures": {
                "totals": [],
                # Clearing house name uses en-dash (U+2013)
                "futures": [{"clearing_house": "ICE\u2013Clear"}],
            }
        },
        historical_series_headers_by_sheet={"Futures": ("ICE-Clear",)},
    )

    assert result["gap_count"] == 0
    assert result["by_sheet"]["Futures"]["clearing_houses_in_data"] == ["ICE-Clear"]
    assert result["by_sheet"]["Futures"]["missing_from_data"] == []
