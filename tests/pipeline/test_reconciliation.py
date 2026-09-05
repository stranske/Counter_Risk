"""Focused reconciliation exception contract tests."""

from __future__ import annotations

from counter_risk.pipeline.parsing_types import UnmappedCounterpartyError
from counter_risk.pipeline.run import reconcile_series_coverage


def test_reconciliation_strict_exception_exposes_normalized_counterparty() -> None:
    try:
        reconcile_series_coverage(
            parsed_data_by_sheet={
                "Total": {"totals": [{"counterparty": "Bank of America, NA"}], "futures": []}
            },
            historical_series_headers_by_sheet={"Total": ("Legacy Counterparty",)},
            fail_policy="strict",
        )
    except UnmappedCounterpartyError as error:
        assert error.normalized_counterparty == "Bank of America"
    else:
        raise AssertionError("Expected UnmappedCounterpartyError")


def test_reconciliation_strict_exception_exposes_raw_counterparty() -> None:
    try:
        reconcile_series_coverage(
            parsed_data_by_sheet={
                "Total": {"totals": [{"counterparty": "Bank of America, NA"}], "futures": []}
            },
            historical_series_headers_by_sheet={"Total": ("Legacy Counterparty",)},
            fail_policy="strict",
        )
    except UnmappedCounterpartyError as error:
        assert error.raw_counterparty == "Bank of America, NA"
    else:
        raise AssertionError("Expected UnmappedCounterpartyError")


def test_reconciliation_warn_mode_records_structured_exception_without_raising() -> None:
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


def test_reconciliation_skips_unmanaged_sheet_when_present_sets_are_authoritative() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "Total": {"totals": [{"counterparty": "Counterparty A"}], "futures": []},
            "WAL": {"totals": [], "futures": []},
        },
        historical_series_headers_by_sheet={
            "Total": ("Counterparty A",),
            "WAL": ("Legacy Counterparty",),
        },
        series_present_by_sheet={"Total": ("Counterparty A",)},
    )

    assert set(result["by_sheet"]) == {"Total"}
    assert result["by_sheet"]["Total"]["counterparties_in_data"] == ["Counterparty A"]
    assert result["missing_series"] == []
    assert result["gap_count"] == 0


def test_reconciliation_prior_populated_treats_absent_series_as_dropped_gap() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "Total": {"totals": [], "futures": []},
        },
        historical_series_headers_by_sheet={
            "Total": ("Active Counterparty", "Dropped Counterparty"),
        },
        prior_populated_series_by_sheet={
            "Total": ("Active Counterparty", "Dropped Counterparty"),
        },
    )

    sheet = result["by_sheet"]["Total"]
    assert sheet["dropped_from_data"] == ["Active Counterparty", "Dropped Counterparty"]
    assert sheet["dormant_from_data"] == []
    assert result["gap_count"] == 2
    assert any("missing from parsed data" in warning for warning in result["warnings"])


def test_reconciliation_prior_populated_classifies_dormant_headers_separately() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "Total": {
                "totals": [{"counterparty": "Active Counterparty"}],
                "futures": [],
            },
        },
        historical_series_headers_by_sheet={
            "Total": ("Active Counterparty", "Dormant Counterparty"),
        },
        prior_populated_series_by_sheet={
            "Total": ("Active Counterparty",),
        },
    )

    sheet = result["by_sheet"]["Total"]
    assert sheet["dropped_from_data"] == []
    assert sheet["dormant_from_data"] == ["Dormant Counterparty"]
    assert result["gap_count"] == 0
    assert any("dormant series" in warning.lower() for warning in result["warnings"])
    assert not any("missing from parsed data" in warning for warning in result["warnings"])


def test_reconciliation_missing_expected_segments_records_gap() -> None:
    result = reconcile_series_coverage(
        parsed_data_by_sheet={
            "Total": {
                "totals": [{"counterparty": "Counterparty A", "segment": "present"}],
                "futures": [],
            },
        },
        historical_series_headers_by_sheet={"Total": ("Counterparty A",)},
        variant="baseline",
        expected_segments_by_variant={"baseline": ("present", "missing-segment")},
    )

    sheet = result["by_sheet"]["Total"]
    assert sheet["missing_expected_segments"] == ["missing-segment"]
    assert result["missing_segments"] == [
        {
            "variant": "baseline",
            "sheet": "Total",
            "expected_segment_identifiers": ["missing-segment"],
        }
    ]
    assert result["gap_count"] == 1
    assert any("expected segments missing" in warning for warning in result["warnings"])
