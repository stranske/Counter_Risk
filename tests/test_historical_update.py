"""Tests for historical workbook update scaffolding."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from counter_risk.writers import historical_update


def test_module_has_expected_sheet_constants() -> None:
    assert historical_update.SHEET_ALL_PROGRAMS_3_YEAR == "All Programs 3 Year"
    assert historical_update.SHEET_EX_LLC_3_YEAR == "ex LLC 3 Year"
    assert historical_update.SHEET_LLC_3_YEAR == "LLC 3 Year"


def test_as_path_rejects_blank_string() -> None:
    with pytest.raises(historical_update.WorkbookValidationError, match="non-empty"):
        historical_update._as_path("", field_name="workbook_path")


def test_validate_workbook_path_rejects_non_xlsx_file(tmp_path: Path) -> None:
    bad_path = tmp_path / "historical.xls"
    bad_path.write_text("not-an-excel-file", encoding="utf-8")

    with pytest.raises(historical_update.WorkbookValidationError, match=r"\.xlsx"):
        historical_update._validate_workbook_path(bad_path)


def test_resolve_append_date_prefers_explicit_date() -> None:
    explicit = date(2026, 1, 31)
    config_date = date(2026, 1, 1)

    resolved = historical_update._resolve_append_date(
        append_date=explicit,
        config_as_of_date=config_date,
    )

    assert resolved == explicit


def test_resolve_append_date_requires_one_source() -> None:
    with pytest.raises(historical_update.AppendDateError, match="required"):
        historical_update._resolve_append_date(append_date=None, config_as_of_date=None)
