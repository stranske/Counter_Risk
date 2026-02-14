"""Robustness tests for raw NISA All Programs parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.parsers.nisa_all_programs import NisaAllProgramsData, parse_nisa_all_programs

_CANONICAL_HEADERS: tuple[str, ...] = (
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
)

_HEADER_LABELS = {
    "counterparty": "Counterparty/ Clearing House",
    "cash": "Cash",
    "tips": "TIPS",
    "treasury": "Treasury",
    "equity": "Equity",
    "commodity": "Commodity",
    "currency": "Currency",
    "notional": "Notional",
    "notional_change": "from prior month***",
    "annualized_volatility": "%",
}


def _set_cell_if_header(
    worksheet: object,
    *,
    row: int,
    header_columns: dict[str, int],
    header_name: str,
    value: object,
) -> None:
    if header_name in header_columns:
        worksheet.cell(row=row, column=header_columns[header_name]).value = value


def _build_raw_nisa_workbook(
    path: Path,
    *,
    sheet_name: str = "Data",
    include_leading_rows: int = 0,
    header_order: tuple[str, ...] = _CANONICAL_HEADERS,
) -> Path:
    openpyxl = pytest.importorskip("openpyxl")

    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_name

    header_row = 4 + include_leading_rows
    for row_number in range(1, header_row - 1):
        worksheet.cell(row=row_number, column=1).value = f"lead-in-{row_number}"

    header_columns: dict[str, int] = {}
    for offset, header_name in enumerate(header_order, start=2):
        header_columns[header_name] = offset
        worksheet.cell(row=header_row, column=offset).value = _HEADER_LABELS[header_name]
    worksheet.cell(row=header_row - 1, column=header_columns["annualized_volatility"]).value = (
        "Annualized Volatility"
    )

    segment_column = 1
    first_ch_row = header_row + 2
    worksheet.cell(row=first_ch_row, column=segment_column).value = "Swaps"
    _set_cell_if_header(
        worksheet,
        row=first_ch_row,
        header_columns=header_columns,
        header_name="counterparty",
        value="Alpha Bank",
    )
    _set_cell_if_header(
        worksheet, row=first_ch_row, header_columns=header_columns, header_name="cash", value=10.0
    )
    _set_cell_if_header(
        worksheet, row=first_ch_row, header_columns=header_columns, header_name="tips", value=20.0
    )
    _set_cell_if_header(
        worksheet,
        row=first_ch_row,
        header_columns=header_columns,
        header_name="treasury",
        value=30.0,
    )
    _set_cell_if_header(
        worksheet, row=first_ch_row, header_columns=header_columns, header_name="equity", value=40.0
    )
    _set_cell_if_header(
        worksheet,
        row=first_ch_row,
        header_columns=header_columns,
        header_name="commodity",
        value=50.0,
    )
    _set_cell_if_header(
        worksheet,
        row=first_ch_row,
        header_columns=header_columns,
        header_name="currency",
        value=60.0,
    )
    _set_cell_if_header(
        worksheet,
        row=first_ch_row,
        header_columns=header_columns,
        header_name="notional",
        value=210.0,
    )
    _set_cell_if_header(
        worksheet,
        row=first_ch_row,
        header_columns=header_columns,
        header_name="notional_change",
        value=5.0,
    )
    _set_cell_if_header(
        worksheet,
        row=first_ch_row,
        header_columns=header_columns,
        header_name="annualized_volatility",
        value=0.11,
    )

    second_ch_row = first_ch_row + 1
    _set_cell_if_header(
        worksheet,
        row=second_ch_row,
        header_columns=header_columns,
        header_name="counterparty",
        value="Beta Bank",
    )
    _set_cell_if_header(
        worksheet, row=second_ch_row, header_columns=header_columns, header_name="cash", value=1.0
    )
    _set_cell_if_header(
        worksheet, row=second_ch_row, header_columns=header_columns, header_name="tips", value=2.0
    )
    _set_cell_if_header(
        worksheet,
        row=second_ch_row,
        header_columns=header_columns,
        header_name="treasury",
        value=3.0,
    )
    _set_cell_if_header(
        worksheet, row=second_ch_row, header_columns=header_columns, header_name="equity", value=4.0
    )
    _set_cell_if_header(
        worksheet,
        row=second_ch_row,
        header_columns=header_columns,
        header_name="commodity",
        value=5.0,
    )
    _set_cell_if_header(
        worksheet,
        row=second_ch_row,
        header_columns=header_columns,
        header_name="currency",
        value=6.0,
    )
    _set_cell_if_header(
        worksheet,
        row=second_ch_row,
        header_columns=header_columns,
        header_name="notional",
        value=21.0,
    )
    _set_cell_if_header(
        worksheet,
        row=second_ch_row,
        header_columns=header_columns,
        header_name="notional_change",
        value=1.0,
    )
    _set_cell_if_header(
        worksheet,
        row=second_ch_row,
        header_columns=header_columns,
        header_name="annualized_volatility",
        value=0.2,
    )

    totals_marker_row = header_row + 20
    worksheet.cell(
        row=totals_marker_row,
        column=header_columns["counterparty"],
    ).value = "Total by Counterparty/Clearing House (This is not the legal obligation exposure)"
    _set_cell_if_header(
        worksheet,
        row=totals_marker_row + 1,
        header_columns=header_columns,
        header_name="counterparty",
        value="Alpha Bank",
    )
    _set_cell_if_header(
        worksheet,
        row=totals_marker_row + 1,
        header_columns=header_columns,
        header_name="tips",
        value=20.0,
    )
    _set_cell_if_header(
        worksheet,
        row=totals_marker_row + 1,
        header_columns=header_columns,
        header_name="treasury",
        value=30.0,
    )
    _set_cell_if_header(
        worksheet,
        row=totals_marker_row + 1,
        header_columns=header_columns,
        header_name="equity",
        value=40.0,
    )
    _set_cell_if_header(
        worksheet,
        row=totals_marker_row + 1,
        header_columns=header_columns,
        header_name="commodity",
        value=50.0,
    )
    _set_cell_if_header(
        worksheet,
        row=totals_marker_row + 1,
        header_columns=header_columns,
        header_name="currency",
        value=60.0,
    )
    _set_cell_if_header(
        worksheet,
        row=totals_marker_row + 1,
        header_columns=header_columns,
        header_name="notional",
        value=210.0,
    )
    _set_cell_if_header(
        worksheet,
        row=totals_marker_row + 1,
        header_columns=header_columns,
        header_name="notional_change",
        value=5.0,
    )
    _set_cell_if_header(
        worksheet,
        row=totals_marker_row + 1,
        header_columns=header_columns,
        header_name="annualized_volatility",
        value=0.11,
    )
    worksheet.cell(row=totals_marker_row + 2, column=header_columns["counterparty"]).value = (
        "Total Current Exposure"
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    workbook.close()
    return path


def _assert_expected_rows(data: NisaAllProgramsData) -> None:
    assert len(data.ch_rows) == 2
    assert data.ch_rows[0].segment == "swaps"
    assert data.ch_rows[0].counterparty == "Alpha Bank"
    assert data.ch_rows[0].cash == pytest.approx(10.0)
    assert data.ch_rows[0].notional == pytest.approx(210.0)
    assert len(data.totals_rows) == 1
    assert data.totals_rows[0].counterparty == "Alpha Bank"
    assert data.totals_rows[0].notional == pytest.approx(210.0)


def test_parse_nisa_all_programs_uses_fixture_file() -> None:
    fixture_path = Path("tests/fixtures/raw_nisa_all_programs.xlsx")
    assert fixture_path.exists(), f"Missing required fixture: {fixture_path}"

    parsed = parse_nisa_all_programs(fixture_path)
    _assert_expected_rows(parsed)


def test_parser_handles_when_data_worksheet_is_not_first_sheet(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    workbook_path = tmp_path / "raw_nisa_non_first_sheet.xlsx"
    data_sheet_name = "NISA Data"
    _build_raw_nisa_workbook(workbook_path, sheet_name=data_sheet_name)

    workbook = openpyxl.load_workbook(workbook_path)
    try:
        first_sheet = workbook.create_sheet("Intro", 0)
        first_sheet.cell(row=1, column=1).value = "Readme"
        workbook.save(workbook_path)
    finally:
        workbook.close()

    parsed = parse_nisa_all_programs(workbook_path)
    _assert_expected_rows(parsed)


def test_parser_handles_extra_leading_rows_before_header_row(tmp_path: Path) -> None:
    workbook_path = tmp_path / "raw_nisa_leading_rows.xlsx"
    _build_raw_nisa_workbook(workbook_path, include_leading_rows=6)

    parsed = parse_nisa_all_programs(workbook_path)
    _assert_expected_rows(parsed)


def test_parser_handles_reordered_columns(tmp_path: Path) -> None:
    workbook_path = tmp_path / "raw_nisa_reordered_columns.xlsx"
    header_order = (
        "tips",
        "counterparty",
        "notional_change",
        "currency",
        "cash",
        "equity",
        "notional",
        "commodity",
        "treasury",
        "annualized_volatility",
    )
    _build_raw_nisa_workbook(workbook_path, header_order=header_order)

    parsed = parse_nisa_all_programs(workbook_path)
    _assert_expected_rows(parsed)


def test_parser_raises_explicit_missing_headers_error(tmp_path: Path) -> None:
    workbook_path = tmp_path / "raw_nisa_missing_headers.xlsx"
    _build_raw_nisa_workbook(
        workbook_path,
        header_order=(
            "counterparty",
            "cash",
            "tips",
            "treasury",
            "equity",
            "notional",
            "notional_change",
            "annualized_volatility",
        ),
    )

    with pytest.raises(ValueError, match="Missing required headers:") as exc_info:
        parse_nisa_all_programs(workbook_path)

    message = str(exc_info.value)
    assert "commodity" in message
    assert "currency" in message
