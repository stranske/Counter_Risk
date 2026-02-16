"""Tests for exposure maturity schedule parser used by WAL."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from counter_risk.parsers.exposure_maturity_schedule import (
    ExposureMaturityColumnsMissingError,
    ExposureMaturityWorkbookLoadError,
    ExposureMaturityWorksheetMissingError,
    parse_exposure_maturity_schedule,
)


def test_parse_exposure_maturity_schedule_fixture() -> None:
    rows = parse_exposure_maturity_schedule(
        Path("tests/fixtures/nisa/NISA_Monthly_Exposure_Summary_sanitized.xlsx")
    )

    assert len(rows) == 6
    assert rows[0].counterparty == "Alpha Clearing"
    assert rows[0].product_type == "Interest Rate Swap"
    assert rows[0].current_exposure == 1250000.0
    assert rows[0].years_to_maturity == 0.5

    assert rows[1].product_type == "Return Swaps"
    assert rows[1].current_exposure == 320000.0
    assert rows[1].years_to_maturity == 2.0


def test_parse_exposure_maturity_schedule_missing_sheet_raises(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    workbook_path = tmp_path / "missing_sheet.xlsx"

    workbook = openpyxl.Workbook()
    workbook.active.title = "Other Sheet"
    workbook.save(workbook_path)
    workbook.close()

    with pytest.raises(ExposureMaturityWorksheetMissingError, match="Missing required worksheet"):
        parse_exposure_maturity_schedule(workbook_path)


def test_parse_exposure_maturity_schedule_workbook_load_failure_is_specific(tmp_path: Path) -> None:
    workbook_path = tmp_path / "not_a_workbook.xlsx"
    workbook_path.write_text("not really an xlsx", encoding="utf-8")

    with pytest.raises(ExposureMaturityWorkbookLoadError, match="Unable to open exposure maturity workbook"):
        parse_exposure_maturity_schedule(workbook_path)


def test_parse_exposure_maturity_schedule_missing_required_header_raises(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    workbook_path = tmp_path / "missing_header.xlsx"

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Exposure Maturity Summary"
    _set_headers(
        sheet,
        headers=[
            "Counterparty",
            "Product Type",
            "Current Exposure",
            # Missing Years to Maturity
        ],
    )
    workbook.save(workbook_path)
    workbook.close()

    with pytest.raises(
        ExposureMaturityColumnsMissingError, match="Missing required headers"
    ):
        parse_exposure_maturity_schedule(workbook_path)


def test_parse_exposure_maturity_schedule_headers_shifted_down_within_scan_range(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    workbook_path = tmp_path / "shifted_headers.xlsx"

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Exposure Maturity Summary"

    # Headers start at row 5 (within the 50-row scan window).
    _set_headers(
        sheet,
        headers=[
            "Counterparty",
            "Product Type",
            "Current Exposure",
            "Years to Maturity",
        ],
        row=5,
    )
    sheet.cell(row=6, column=1).value = "Alpha"
    sheet.cell(row=6, column=2).value = "Repo"
    sheet.cell(row=6, column=3).value = 100.0
    sheet.cell(row=6, column=4).value = 2.0

    workbook.save(workbook_path)
    workbook.close()

    rows = parse_exposure_maturity_schedule(workbook_path)
    assert len(rows) == 1
    assert rows[0].counterparty == "Alpha"
    assert rows[0].product_type == "Repo"
    assert rows[0].current_exposure == 100.0
    assert rows[0].years_to_maturity == 2.0


def _set_headers(worksheet: Any, headers: list[str], *, row: int = 1) -> None:
    for index, header in enumerate(headers, start=1):
        worksheet.cell(row=row, column=index).value = header
