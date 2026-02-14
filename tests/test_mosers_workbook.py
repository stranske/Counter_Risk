"""Tests for data-driven MOSERS workbook generation."""

from __future__ import annotations

from pathlib import Path
from shutil import copyfile

import pytest

from counter_risk.mosers.workbook_generation import generate_mosers_workbook
from counter_risk.parsers.nisa import parse_nisa_all_programs


@pytest.mark.parametrize("fixture_path", [Path("tests/fixtures/raw_nisa_all_programs.xlsx")])
def test_generate_mosers_workbook_populates_program_name_from_parsed_nisa_data(
    fixture_path: Path,
) -> None:
    parsed = parse_nisa_all_programs(fixture_path)

    workbook = generate_mosers_workbook(fixture_path)
    try:
        worksheet = workbook["CPRS - CH"]
        assert worksheet["B5"].value == parsed.ch_rows[0].counterparty
        expected_vols = _pad_to_slot_count(
            [row.annualized_volatility for row in parsed.totals_rows], 11
        )
        expected_allocations = _pad_to_slot_count(_expected_allocations(parsed), 11)
        assert _read_column_values(worksheet, "D", 10, 20) == expected_vols
        assert _read_column_values(worksheet, "E", 10, 20) == expected_allocations
    finally:
        workbook.close()


def test_generate_mosers_workbook_reflects_input_annualized_volatility_changes(
    tmp_path: Path,
) -> None:
    openpyxl = pytest.importorskip("openpyxl")

    base_input = Path("tests/fixtures/raw_nisa_all_programs.xlsx")
    variant_input = tmp_path / "raw_nisa_all_programs_variant.xlsx"
    copyfile(base_input, variant_input)

    source_workbook = openpyxl.load_workbook(variant_input)
    try:
        changed = _bump_first_annualized_volatility_column(source_workbook)
        assert changed, "Failed to edit annualized volatility values in fixture copy"
        source_workbook.save(variant_input)
    finally:
        source_workbook.close()

    base_workbook = generate_mosers_workbook(base_input)
    variant_workbook = generate_mosers_workbook(variant_input)
    try:
        base_d10 = base_workbook["CPRS - CH"]["D10"].value
        variant_d10 = variant_workbook["CPRS - CH"]["D10"].value
        assert base_d10 != variant_d10
    finally:
        base_workbook.close()
        variant_workbook.close()


def _bump_first_annualized_volatility_column(workbook: object) -> bool:
    for sheet_name in workbook.sheetnames:
        worksheet = workbook[sheet_name]
        max_row = int(worksheet.max_row)
        max_col = int(worksheet.max_column)

        target_col = 0
        header_row = 0
        for row_number in range(1, min(max_row, 200) + 1):
            for col_number in range(1, max_col + 1):
                value = worksheet.cell(row=row_number, column=col_number).value
                text = " ".join(str(value or "").split()).strip().casefold()
                if "annualized volatility" in text:
                    target_col = col_number
                    header_row = row_number
                    break
            if target_col:
                break

        if not target_col:
            continue

        edited = False
        for row_number in range(header_row + 1, max_row + 1):
            cell = worksheet.cell(row=row_number, column=target_col)
            value = cell.value
            if isinstance(value, (int, float)):
                cell.value = float(value) + 0.25
                edited = True

        if edited:
            return True

    return False


def _read_column_values(
    worksheet: object, column: str, start_row: int, end_row: int
) -> list[float | None]:
    return [
        worksheet[f"{column}{row_number}"].value for row_number in range(start_row, end_row + 1)
    ]


def _expected_allocations(parsed_data: object) -> list[float]:
    total_notional = sum(row.notional for row in parsed_data.totals_rows)
    if total_notional == 0:
        return [0.0 for _ in parsed_data.totals_rows]
    return [row.notional / total_notional for row in parsed_data.totals_rows]


def _pad_to_slot_count(values: list[float], slots: int) -> list[float | None]:
    if len(values) >= slots:
        return values[:slots]
    return [*values, *([None] * (slots - len(values)))]
