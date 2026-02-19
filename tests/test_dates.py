"""Tests for date derivation helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from counter_risk.config import WorkflowConfig
from counter_risk.dates import derive_as_of_date


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
