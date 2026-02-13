"""Tests for historical workbook update scaffolding."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

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


class _FakeCell:
    def __init__(self, value: Any = None) -> None:
        self.value = value


class _FakeWorksheet:
    def __init__(self, title: str) -> None:
        self.title = title
        self.max_row = 1
        self.max_column = 1
        self._cells: dict[tuple[int, int], _FakeCell] = {}

    def cell(self, row: int, column: int) -> _FakeCell:
        self.max_row = max(self.max_row, row)
        self.max_column = max(self.max_column, column)
        key = (row, column)
        if key not in self._cells:
            self._cells[key] = _FakeCell()
        return self._cells[key]

    def set_value(self, row: int, column: int, value: Any) -> None:
        self.cell(row=row, column=column).value = value


class _FakeWorkbook:
    def __init__(self, sheets: dict[str, _FakeWorksheet]) -> None:
        self._sheets = sheets
        self.sheetnames = list(sheets)
        self.closed_count = 0
        self.saved_paths: list[Path] = []

    def __getitem__(self, item: str) -> _FakeWorksheet:
        return self._sheets[item]

    def save(self, path: Path) -> None:
        self.saved_paths.append(path)

    def close(self) -> None:
        self.closed_count += 1


def _build_sheet(sheet_name: str, series: tuple[str, ...]) -> _FakeWorksheet:
    sheet = _FakeWorksheet(sheet_name)
    sheet.set_value(1, 1, "Date")
    for offset, name in enumerate(series, start=2):
        sheet.set_value(1, offset, name)
    sheet.set_value(2, 1, date(2025, 12, 31))
    for offset, _ in enumerate(series, start=2):
        sheet.set_value(2, offset, 1.0)
    return sheet


def _seed_real_sheet(worksheet: Any, series: tuple[str, ...]) -> None:
    worksheet.cell(row=1, column=1).value = "Date"
    for offset, name in enumerate(series, start=2):
        worksheet.cell(row=1, column=offset).value = name

    worksheet.cell(row=2, column=1).value = date(2025, 12, 31)
    for offset, _ in enumerate(series, start=2):
        worksheet.cell(row=2, column=offset).value = 1.0


def test_append_functions_save_and_reload_updated_workbook(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    workbook_path = tmp_path / "historical.xlsx"

    workbook = openpyxl.Workbook()
    all_programs = workbook.active
    all_programs.title = historical_update.SHEET_ALL_PROGRAMS_3_YEAR
    _seed_real_sheet(
        all_programs,
        historical_update.SERIES_BY_SHEET[historical_update.SHEET_ALL_PROGRAMS_3_YEAR],
    )

    ex_trend = workbook.create_sheet(historical_update.SHEET_EX_LLC_3_YEAR)
    _seed_real_sheet(
        ex_trend,
        historical_update.SERIES_BY_SHEET[historical_update.SHEET_EX_LLC_3_YEAR],
    )

    trend = workbook.create_sheet(historical_update.SHEET_LLC_3_YEAR)
    _seed_real_sheet(
        trend,
        historical_update.SERIES_BY_SHEET[historical_update.SHEET_LLC_3_YEAR],
    )

    workbook.save(workbook_path)
    workbook.close()

    as_of_date = date(2026, 1, 31)
    historical_update.append_row_all_programs(
        workbook_path=workbook_path,
        rollup_data={"Total": 100.0, "Cash": 25.0},
        config_as_of_date=as_of_date,
    )
    historical_update.append_row_ex_trend(
        workbook_path=workbook_path,
        rollup_data={"Total": 200.0, "Class": 50.0},
        config_as_of_date=as_of_date,
    )
    historical_update.append_row_trend(
        workbook_path=workbook_path,
        rollup_data={"Total": 300.0, "Equity": 75.0},
        config_as_of_date=as_of_date,
    )

    reloaded = openpyxl.load_workbook(workbook_path)
    try:
        for sheet_name in (
            historical_update.SHEET_ALL_PROGRAMS_3_YEAR,
            historical_update.SHEET_EX_LLC_3_YEAR,
            historical_update.SHEET_LLC_3_YEAR,
        ):
            sheet = reloaded[sheet_name]
            assert sheet.max_row == 3

            headers = historical_update._build_header_map(sheet, header_row=1)
            date_column = historical_update._get_date_column(headers)
            assert (
                historical_update._coerce_cell_date(sheet.cell(row=3, column=date_column).value)
                == as_of_date
            )
    finally:
        reloaded.close()


def test_append_functions_add_exactly_one_row_to_each_target_sheet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workbook_path = tmp_path / "historical.xlsx"
    workbook_path.write_text("placeholder", encoding="utf-8")

    all_programs = _build_sheet(
        historical_update.SHEET_ALL_PROGRAMS_3_YEAR,
        historical_update.SERIES_BY_SHEET[historical_update.SHEET_ALL_PROGRAMS_3_YEAR],
    )
    ex_trend = _build_sheet(
        historical_update.SHEET_EX_LLC_3_YEAR,
        historical_update.SERIES_BY_SHEET[historical_update.SHEET_EX_LLC_3_YEAR],
    )
    trend = _build_sheet(
        historical_update.SHEET_LLC_3_YEAR,
        historical_update.SERIES_BY_SHEET[historical_update.SHEET_LLC_3_YEAR],
    )
    workbook = _FakeWorkbook(
        {
            historical_update.SHEET_ALL_PROGRAMS_3_YEAR: all_programs,
            historical_update.SHEET_EX_LLC_3_YEAR: ex_trend,
            historical_update.SHEET_LLC_3_YEAR: trend,
        }
    )

    fake_module = ModuleType("openpyxl")
    fake_module.load_workbook = lambda filename: workbook  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openpyxl", fake_module)

    as_of_date = date(2026, 1, 31)
    row_counts_before = {
        historical_update.SHEET_ALL_PROGRAMS_3_YEAR: all_programs.max_row,
        historical_update.SHEET_EX_LLC_3_YEAR: ex_trend.max_row,
        historical_update.SHEET_LLC_3_YEAR: trend.max_row,
    }

    historical_update.append_row_all_programs(
        workbook_path=workbook_path,
        rollup_data={"Total": 11.0, "Cash": 3.5},
        config_as_of_date=as_of_date,
    )
    historical_update.append_row_ex_trend(
        workbook_path=workbook_path,
        rollup_data={"Total": 12.0, "Class": 4.5},
        config_as_of_date=as_of_date,
    )
    historical_update.append_row_trend(
        workbook_path=workbook_path,
        rollup_data={"Total": 13.0, "Class": 5.5},
        config_as_of_date=as_of_date,
    )

    assert all_programs.max_row == row_counts_before[historical_update.SHEET_ALL_PROGRAMS_3_YEAR] + 1
    assert ex_trend.max_row == row_counts_before[historical_update.SHEET_EX_LLC_3_YEAR] + 1
    assert trend.max_row == row_counts_before[historical_update.SHEET_LLC_3_YEAR] + 1

    assert all_programs.cell(row=3, column=1).value == as_of_date
    assert ex_trend.cell(row=3, column=1).value == as_of_date
    assert trend.cell(row=3, column=1).value == as_of_date

    assert workbook.saved_paths == [workbook_path, workbook_path, workbook_path]
    assert workbook.closed_count == 3


def test_append_functions_write_known_series_values_with_numeric_edge_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workbook_path = tmp_path / "historical.xlsx"
    workbook_path.write_text("placeholder", encoding="utf-8")

    all_programs = _build_sheet(
        historical_update.SHEET_ALL_PROGRAMS_3_YEAR,
        historical_update.SERIES_BY_SHEET[historical_update.SHEET_ALL_PROGRAMS_3_YEAR],
    )
    ex_trend = _build_sheet(
        historical_update.SHEET_EX_LLC_3_YEAR,
        historical_update.SERIES_BY_SHEET[historical_update.SHEET_EX_LLC_3_YEAR],
    )
    trend = _build_sheet(
        historical_update.SHEET_LLC_3_YEAR,
        historical_update.SERIES_BY_SHEET[historical_update.SHEET_LLC_3_YEAR],
    )
    workbook = _FakeWorkbook(
        {
            historical_update.SHEET_ALL_PROGRAMS_3_YEAR: all_programs,
            historical_update.SHEET_EX_LLC_3_YEAR: ex_trend,
            historical_update.SHEET_LLC_3_YEAR: trend,
        }
    )

    fake_module = ModuleType("openpyxl")
    fake_module.load_workbook = lambda filename: workbook  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openpyxl", fake_module)

    as_of_date = date(2026, 1, 31)
    all_programs_rollups = {
        "Total": 0.0,
        "Cash": -12.75,
        "Commodity": 1_250_000_000_000.0,
    }
    ex_trend_rollups = {
        "Total": 222.125,
        "Class": -9.5,
        "Currency": 0.0,
    }
    trend_rollups = {
        "Total": 3_400_000_000.0,
        "Equity": 0.0,
        "Commodity": -0.25,
    }

    historical_update.append_row_all_programs(
        workbook_path=workbook_path,
        rollup_data=all_programs_rollups,
        config_as_of_date=as_of_date,
    )
    historical_update.append_row_ex_trend(
        workbook_path=workbook_path,
        rollup_data=ex_trend_rollups,
        config_as_of_date=as_of_date,
    )
    historical_update.append_row_trend(
        workbook_path=workbook_path,
        rollup_data=trend_rollups,
        config_as_of_date=as_of_date,
    )

    all_headers = historical_update._build_header_map(all_programs, header_row=1)
    ex_headers = historical_update._build_header_map(ex_trend, header_row=1)
    trend_headers = historical_update._build_header_map(trend, header_row=1)

    assert all_programs.cell(row=3, column=all_headers["total"]).value == pytest.approx(0.0)
    assert all_programs.cell(row=3, column=all_headers["cash"]).value == pytest.approx(-12.75)
    assert all_programs.cell(row=3, column=all_headers["commodity"]).value == pytest.approx(
        1_250_000_000_000.0
    )

    assert ex_trend.cell(row=3, column=ex_headers["total"]).value == pytest.approx(222.125)
    assert ex_trend.cell(row=3, column=ex_headers["class"]).value == pytest.approx(-9.5)
    assert ex_trend.cell(row=3, column=ex_headers["currency"]).value == pytest.approx(0.0)

    assert trend.cell(row=3, column=trend_headers["total"]).value == pytest.approx(3_400_000_000.0)
    assert trend.cell(row=3, column=trend_headers["equity"]).value == pytest.approx(0.0)
    assert trend.cell(row=3, column=trend_headers["commodity"]).value == pytest.approx(-0.25)

    assert workbook.closed_count == 3
