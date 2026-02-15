"""Tests for exposure maturity schedule parser used by WAL."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from counter_risk.parsers.exposure_maturity_schedule import parse_exposure_maturity_schedule


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

    with pytest.raises(ValueError, match="Missing required worksheet"):
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

    with pytest.raises(ValueError, match="Missing required headers"):
        parse_exposure_maturity_schedule(workbook_path)


def _set_headers(worksheet: Any, headers: list[str]) -> None:
    for index, header in enumerate(headers, start=1):
        worksheet.cell(row=1, column=index).value = header
