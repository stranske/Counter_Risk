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
