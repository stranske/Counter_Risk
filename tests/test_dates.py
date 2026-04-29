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
