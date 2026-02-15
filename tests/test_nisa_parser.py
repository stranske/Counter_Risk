"""Focused tests for NISA worksheet selection and header alias behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from counter_risk.parsers.nisa import parse_nisa_all_programs

_HEADERS = {
    "counterparty": "Counterparty/ Clearing House",
    "cash": "Cash",
    "tips": "TIPS",
    "treasury": "Treasury",
    "equity": "Equity",
    "commodity": "Commodity",
    "currency": "Currency",
    "notional": "Notional",
    "notional_change": "from prior month***",
    "annualized_volatility": "Annualized Volatility",
}


def test_parser_falls_back_when_highest_scoring_sheet_is_missing_required_headers(
    tmp_path: Path,
) -> None:
    openpyxl = pytest.importorskip("openpyxl")

    workbook_path = tmp_path / "nisa_fallback.xlsx"
    workbook = openpyxl.Workbook()
    try:
        almost = workbook.active
        almost.title = "Almost"
        _populate_minimal_nisa_sheet(
            almost, counterparty_name="Almost Alpha", drop_headers={"currency"}
        )

        valid = workbook.create_sheet("Valid")
        _populate_minimal_nisa_sheet(valid, counterparty_name="Valid Alpha")

        workbook.save(workbook_path)
    finally:
        workbook.close()

    parsed = parse_nisa_all_programs(workbook_path)
    assert parsed.ch_rows[0].counterparty == "Valid Alpha"


def test_parser_does_not_map_standalone_percent_header_to_annualized_volatility(
    tmp_path: Path,
) -> None:
    openpyxl = pytest.importorskip("openpyxl")

    workbook_path = tmp_path / "nisa_percent_only_header.xlsx"
    workbook = openpyxl.Workbook()
    try:
        sheet = workbook.active
        sheet.title = "Percent Header"
        _populate_minimal_nisa_sheet(
            sheet,
            counterparty_name="Alpha",
            annualized_vol_header="%",
            annualized_vol_helper_header="",
        )
        workbook.save(workbook_path)
    finally:
        workbook.close()

    with pytest.raises(ValueError, match="Missing required headers:") as exc_info:
        parse_nisa_all_programs(workbook_path)

    message = str(exc_info.value)
    assert "annualized_volatility" in message
    assert "Percent Header" in message


def _populate_minimal_nisa_sheet(
    worksheet: Any,
    *,
    counterparty_name: str,
    drop_headers: set[str] | None = None,
    annualized_vol_header: str | None = None,
    annualized_vol_helper_header: str = "Annualized Volatility",
) -> None:
    drop_headers = drop_headers or set()
    header_row = 4
    headers = [
        "counterparty",
        "cash",
        "tips",
        "treasury",
        "equity",
        "commodity",
        "currency",
        "notional",
        "notional_change",
        "annualized_volatility",
    ]

    column = 2
    header_columns: dict[str, int] = {}
    for header in headers:
        if header in drop_headers:
            continue
        header_columns[header] = column
        if header == "annualized_volatility":
            worksheet.cell(
                row=header_row,
                column=column,
            ).value = (
                annualized_vol_header if annualized_vol_header is not None else _HEADERS[header]
            )
            worksheet.cell(row=header_row - 1, column=column).value = annualized_vol_helper_header
        else:
            worksheet.cell(row=header_row, column=column).value = _HEADERS[header]
        column += 1

    first_data_row = header_row + 2
    worksheet.cell(row=first_data_row, column=1).value = "Swaps"
    if "counterparty" in header_columns:
        worksheet.cell(row=first_data_row, column=header_columns["counterparty"]).value = (
            counterparty_name
        )
    for numeric_header in (
        "cash",
        "tips",
        "treasury",
        "equity",
        "commodity",
        "currency",
        "notional",
        "notional_change",
        "annualized_volatility",
    ):
        if numeric_header in header_columns:
            worksheet.cell(row=first_data_row, column=header_columns[numeric_header]).value = 1.0

    totals_marker_row = 20
    if "counterparty" in header_columns:
        worksheet.cell(row=totals_marker_row, column=header_columns["counterparty"]).value = (
            "Total by Counterparty/Clearing House"
        )
        worksheet.cell(row=totals_marker_row + 1, column=header_columns["counterparty"]).value = (
            counterparty_name
        )
        worksheet.cell(row=totals_marker_row + 2, column=header_columns["counterparty"]).value = (
            "Total Current Exposure"
        )

    for numeric_header in (
        "tips",
        "treasury",
        "equity",
        "commodity",
        "currency",
        "notional",
        "notional_change",
        "annualized_volatility",
    ):
        if numeric_header in header_columns:
            worksheet.cell(
                row=totals_marker_row + 1, column=header_columns[numeric_header]
            ).value = 1.0
