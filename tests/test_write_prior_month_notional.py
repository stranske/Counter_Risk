"""Tests for duplicate-key handling in write_prior_month_notional."""

from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.io import DuplicateDescriptionError
from counter_risk.io.mosers_workbook import (
    load_mosers_workbook,
    locate_futures_detail_section,
    write_prior_month_notional,
    writeback_prior_month_notionals,
)

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mosers_workbook_fixture.xlsx"


def _duplicate_rows() -> list[dict[str, float | str]]:
    return [
        {"description": "US 2-Year Note (CBT) Mar25", "prior_notional": 101.0},
        {"description": "US 2-Year   Note (CBT)   March 2025", "prior_notional": 202.0},
    ]


def test_write_prior_month_notional_detects_duplicate_normalized_description() -> None:
    wb = load_mosers_workbook(_FIXTURE_PATH)
    section = locate_futures_detail_section(wb)

    with pytest.raises(DuplicateDescriptionError):
        write_prior_month_notional(wb, section, _duplicate_rows())


def test_duplicate_description_error_exposes_key_and_row_indices() -> None:
    wb = load_mosers_workbook(_FIXTURE_PATH)
    section = locate_futures_detail_section(wb)

    with pytest.raises(DuplicateDescriptionError) as exc_info:
        write_prior_month_notional(wb, section, _duplicate_rows())

    err = exc_info.value
    assert err.duplicate_key == "US 2-YEAR NOTE (CBT) MAR25"
    assert err.row_indices == [0, 1]


def test_duplicates_raise_before_any_write_side_effects(tmp_path: Path) -> None:
    wb = load_mosers_workbook(_FIXTURE_PATH)
    section = locate_futures_detail_section(wb)
    ws = wb[section.sheet_name]
    prior_col_values_before = [
        ws.cell(row=r, column=section.prior_month_col).value
        for r in range(section.data_start_row, section.data_end_row + 1)
    ]

    with pytest.raises(DuplicateDescriptionError):
        write_prior_month_notional(wb, section, _duplicate_rows())

    prior_col_values_after = [
        ws.cell(row=r, column=section.prior_month_col).value
        for r in range(section.data_start_row, section.data_end_row + 1)
    ]
    assert prior_col_values_after == prior_col_values_before

    output_path = tmp_path / "should_not_exist.xlsx"
    with pytest.raises(DuplicateDescriptionError):
        writeback_prior_month_notionals(
            source_path=_FIXTURE_PATH,
            output_path=output_path,
            rows=_duplicate_rows(),
        )
    assert not output_path.exists()
