"""Tests for date derivation helpers."""

from __future__ import annotations

from datetime import UTC, date
from pathlib import Path

import pytest

from counter_risk.config import WorkflowConfig
from counter_risk.dates import (
    AS_OF_SOURCE_CONFIG,
    AS_OF_SOURCE_HEADER_MAPPING,
    AS_OF_SOURCE_HEADER_TEXT,
    RUN_DATE_SOURCE_CONFIG,
    RUN_DATE_SOURCE_SYSTEM_CLOCK,
    derive_as_of_date,
    derive_run_date,
    resolve_as_of_date,
    resolve_run_date,
)


def _config(*, as_of_date: date | None) -> WorkflowConfig:
    return WorkflowConfig(
        as_of_date=as_of_date,
        mosers_all_programs_xlsx=Path("all.xlsx"),
        mosers_ex_trend_xlsx=Path("ex.xlsx"),
        mosers_trend_xlsx=Path("trend.xlsx"),
        hist_all_programs_3yr_xlsx=Path("hist_all.xlsx"),
        hist_ex_llc_3yr_xlsx=Path("hist_ex.xlsx"),
        hist_llc_3yr_xlsx=Path("hist_trend.xlsx"),
        monthly_pptx=Path("monthly.pptx"),
    )


def test_derive_as_of_date_prefers_config_value_over_cprs_headers() -> None:
    config = _config(as_of_date=date(2026, 1, 31))

    derived = derive_as_of_date(config, {"CPRS CH Header Date": "02/28/2026"})

    assert derived == date(2026, 1, 31)


def test_derive_as_of_date_uses_cprs_mapping_when_config_missing() -> None:
    config = _config(as_of_date=None)

    derived = derive_as_of_date(config, {"CPRS CH Header Date": "01/31/2026"})

    assert derived == date(2026, 1, 31)


def test_derive_as_of_date_uses_cprs_header_text_tokens_when_config_missing() -> None:
    config = _config(as_of_date=None)

    derived = derive_as_of_date(
        config,
        [
            "Counterparty Risk Summary",
            "As Of Date: 2026-01-31",
        ],
    )

    assert derived == date(2026, 1, 31)


def test_derive_as_of_date_raises_clear_error_when_no_valid_source() -> None:
    config = _config(as_of_date=None)

    with pytest.raises(ValueError, match="Unable to derive as_of_date"):
        derive_as_of_date(config, {"header": "not a date"})


def test_derive_run_date_prefers_config_value() -> None:
    config = _config(as_of_date=None).model_copy(update={"run_date": date(2026, 2, 14)})

    derived = derive_run_date(config)

    assert derived == date(2026, 2, 14)


def test_derive_run_date_is_deterministic_for_explicit_timezone() -> None:
    config = _config(as_of_date=None)

    first = derive_run_date(config, tzinfo=UTC)
    second = derive_run_date(config, tzinfo=UTC)

    assert first == second


def test_resolve_as_of_date_records_config_source() -> None:
    config = _config(as_of_date=date(2026, 3, 31))

    resolution = resolve_as_of_date(config, {"CPRS CH Header Date": "02/28/2026"})

    assert resolution.value == date(2026, 3, 31)
    assert resolution.source == AS_OF_SOURCE_CONFIG
    assert resolution.details == {"config_field": "as_of_date"}


def test_resolve_as_of_date_records_header_mapping_source() -> None:
    config = _config(as_of_date=None)

    resolution = resolve_as_of_date(config, {"CPRS CH Header Date": "02/28/2026"})

    assert resolution.value == date(2026, 2, 28)
    assert resolution.source == AS_OF_SOURCE_HEADER_MAPPING
    assert resolution.details["header_label"] == "CPRS CH Header Date"
    assert resolution.details["raw_value"] == "02/28/2026"


def test_resolve_as_of_date_records_header_text_source() -> None:
    config = _config(as_of_date=None)

    resolution = resolve_as_of_date(
        config,
        ["Counterparty Risk Summary", "As Of Date: 2026-01-31"],
    )

    assert resolution.value == date(2026, 1, 31)
    assert resolution.source == AS_OF_SOURCE_HEADER_TEXT
    assert resolution.details["header_text"] == "As Of Date: 2026-01-31"
    assert resolution.details["matched_token"] == "2026-01-31"


def test_resolve_as_of_date_raises_when_unresolved() -> None:
    config = _config(as_of_date=None)

    with pytest.raises(ValueError, match="Unable to derive as_of_date"):
        resolve_as_of_date(config, {"header": "not a date"})


def test_resolve_run_date_records_config_source() -> None:
    config = _config(as_of_date=None).model_copy(update={"run_date": date(2026, 4, 1)})

    resolution = resolve_run_date(config)

    assert resolution.value == date(2026, 4, 1)
    assert resolution.source == RUN_DATE_SOURCE_CONFIG
    assert resolution.details == {"config_field": "run_date"}


def test_resolve_run_date_records_system_clock_source_when_unset() -> None:
    config = _config(as_of_date=None)

    resolution = resolve_run_date(config, tzinfo=UTC)

    assert isinstance(resolution.value, date)
    assert resolution.source == RUN_DATE_SOURCE_SYSTEM_CLOCK
    assert resolution.details["tzinfo"] == "UTC"


def test_resolve_as_of_date_to_manifest_entry_is_json_friendly() -> None:
    config = _config(as_of_date=None)

    resolution = resolve_as_of_date(config, {"CPRS CH Header Date": "02/28/2026"})
    entry = resolution.to_manifest_entry()

    assert entry == {
        "value": "2026-02-28",
        "source": AS_OF_SOURCE_HEADER_MAPPING,
        "details": {
            "header_label": "CPRS CH Header Date",
            "raw_value": "02/28/2026",
        },
    }


def test_compare_source_dates_detects_later_variant_without_changing_precedence() -> None:
    from counter_risk.dates import compare_source_report_dates, source_report_date_evidence

    config = _config(as_of_date=date(2026, 1, 31))
    evidence = [
        source_report_date_evidence(
            variant=variant, path=f"{variant}.xlsx", headers=[f"Report Date: {value}"]
        )
        for variant, value in (("all_programs", "2026-01-31"), ("trend", "2026-02-28"))
    ]
    comparison = compare_source_report_dates(configured_date=config.as_of_date, evidence=evidence)
    assert comparison["has_conflict"] is True
    assert comparison["config_conflict_variants"] == ["trend"]
    assert comparison["inter_variant_conflict"] is True
    assert comparison["sources"][1]["path"] == "trend.xlsx"
    assert resolve_as_of_date(config, ["Report Date: 2026-02-28"]).value == date(2026, 1, 31)


@pytest.mark.parametrize(
    "headers,status",
    [
        ([], "unverified"),
        (["Created 2026-02-28", "Settlement 2026-01-31"], "unverified"),
        (["Prior report date: 2026-02-28"], "unverified"),
        (["Report date: missing; last updated 2026-02-28"], "ambiguous"),
        (["Report date: 2026-01-310"], "ambiguous"),
        (["Report date: 2026-01-31T23:00:00"], "ambiguous"),
        (["Report date: 2026-01-31", "As of date: 2026-02-28"], "ambiguous"),
        (["Report date: 2026-01-31 / 2026-02-28"], "ambiguous"),
        (["Report date: 2026-01-31", "Report date: invalid"], "ambiguous"),
        (["CPRS CH Header Date 2026-01-31"], "generated"),
        (["Report date: 2026-01-31", "Generated from config as_of_date"], "generated"),
    ],
)
def test_unverified_source_dates_never_confirm_match_or_conflict(headers, status) -> None:
    from counter_risk.dates import compare_source_report_dates, source_report_date_evidence

    evidence = source_report_date_evidence(variant="trend", path="trend.xlsx", headers=headers)
    assert evidence["status"] == status
    assert evidence["report_date"] is None
    result = compare_source_report_dates(configured_date=date(2026, 1, 31), evidence=[evidence])
    assert result["has_conflict"] is False
    assert result["status"] == "unverified"


@pytest.mark.parametrize(
    "header",
    [
        "Report Date: 2026-02-28 / 2026-01-310",
        "Report Date: 2026-01-31 / 2026-02-28T23:00:00",
        "Report Date: 01/31/2026 / 02/28/20260",
        "Report Date: 2026-01-31 / 2026-02-28_extra",
    ],
)
def test_malformed_additional_date_cannot_confirm_source_period(header: str) -> None:
    from counter_risk.dates import compare_source_report_dates, source_report_date_evidence

    evidence = source_report_date_evidence(variant="trend", path="trend.xlsx", headers=[header])
    assert evidence["status"] == "ambiguous"
    assert evidence["report_date"] is None
    comparison = compare_source_report_dates(configured_date=date(2026, 1, 31), evidence=[evidence])
    assert comparison["status"] == "unverified"
    assert comparison["has_conflict"] is False
    # The narrower evidence grammar must not change config or legacy fallback resolution.
    assert resolve_as_of_date(_config(as_of_date=date(2026, 1, 31)), [header]).value == date(
        2026, 1, 31
    )
    expected_fallback = (
        date(2026, 2, 28) if header.startswith("Report Date: 2026-02") else date(2026, 1, 31)
    )
    assert resolve_as_of_date(_config(as_of_date=None), [header]).value == expected_fallback


@pytest.mark.parametrize(
    "header,expected",
    [
        ("Report Date: 2026-01-31", date(2026, 1, 31)),
        ("REPORT_DATE 1/31/2026", date(2026, 1, 31)),
        ("as-of-date: 01/31/26", date(2026, 1, 31)),
        ("As Of 1/31/68", date(2068, 1, 31)),
        ("Report-Date: 1/31/69", date(1969, 1, 31)),
    ],
)
def test_source_date_formats_compare_as_calendar_dates(header: str, expected: date) -> None:
    from counter_risk.dates import compare_source_report_dates, source_report_date_evidence

    evidence = source_report_date_evidence(variant="trend", path="trend.xlsx", headers=[header])
    assert evidence["status"] == "identified"
    assert evidence["report_date"] == expected.isoformat()
    comparison = compare_source_report_dates(configured_date=expected, evidence=[evidence])
    assert comparison["status"] == "consistent"
    assert comparison["has_conflict"] is False
