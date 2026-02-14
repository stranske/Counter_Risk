"""Data-driven MOSERS workbook generation from raw NISA inputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from counter_risk.mosers.template import load_mosers_template_workbook
from counter_risk.parsers.nisa import parse_nisa_all_programs

_TARGET_SHEET = "CPRS - CH"
_PROGRAM_NAME_CELL = "B5"
_VOL_COLUMN = "D"
_ALLOCATION_COLUMN = "E"
_START_ROW = 10
_END_ROW = 20


def generate_mosers_workbook(raw_nisa_path: str | Path) -> Any:
    """Generate a populated MOSERS workbook from raw NISA input.

    The internal MOSERS template workbook is loaded from package resources,
    parsed NISA values are written to fixed target cells/ranges, and the
    populated openpyxl workbook is returned without writing it to disk.
    """

    parsed = parse_nisa_all_programs(raw_nisa_path)
    workbook = load_mosers_template_workbook()

    worksheet = workbook[_TARGET_SHEET] if _TARGET_SHEET in workbook.sheetnames else workbook.active
    first_program = parsed.ch_rows[0].counterparty if parsed.ch_rows else ""
    worksheet[_PROGRAM_NAME_CELL] = first_program

    annualized_vols = [row.annualized_volatility for row in parsed.totals_rows]
    allocation_percentages = _build_allocation_percentages(parsed.totals_rows)

    _write_vertical_values(
        worksheet=worksheet,
        column_letter=_VOL_COLUMN,
        start_row=_START_ROW,
        end_row=_END_ROW,
        values=annualized_vols,
    )
    _write_vertical_values(
        worksheet=worksheet,
        column_letter=_ALLOCATION_COLUMN,
        start_row=_START_ROW,
        end_row=_END_ROW,
        values=allocation_percentages,
    )

    return workbook


def _build_allocation_percentages(totals_rows: tuple[Any, ...]) -> list[float]:
    total_notional = sum(float(getattr(row, "notional", 0.0)) for row in totals_rows)
    if total_notional == 0:
        return [0.0 for _ in totals_rows]
    return [float(getattr(row, "notional", 0.0)) / total_notional for row in totals_rows]


def _write_vertical_values(
    *,
    worksheet: Any,
    column_letter: str,
    start_row: int,
    end_row: int,
    values: list[float],
) -> None:
    """Write values into a contiguous column range and clear remaining cells."""

    total_slots = (end_row - start_row) + 1
    for index in range(total_slots):
        row_number = start_row + index
        cell = f"{column_letter}{row_number}"
        worksheet[cell] = values[index] if index < len(values) else None
