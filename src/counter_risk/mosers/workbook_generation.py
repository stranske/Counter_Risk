"""Data-driven MOSERS workbook generation from raw NISA inputs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeAlias

from counter_risk.mosers.template import load_mosers_template_workbook
from counter_risk.parsers.nisa import (
    NisaAllProgramsData,
    NisaTotalsRow,
    parse_nisa_all_programs,
)
from counter_risk.parsers.nisa_ex_trend import parse_nisa_ex_trend
from counter_risk.parsers.nisa_trend import parse_nisa_trend

Workbook: TypeAlias = Any
Worksheet: TypeAlias = Any

_REQUIRED_SHEETS = ("CPRS - CH", "CPRS - FCM")
_TARGET_SHEET = "CPRS - CH"
_PROGRAM_NAME_CELL = "B5"
_VOL_COLUMN = "D"
_ALLOCATION_COLUMN = "E"
_START_ROW = 10
_END_ROW = 20


@dataclass(frozen=True)
class MosersAllProgramsOutputStructure:
    """Expected MOSERS workbook layout for All Programs generation."""

    required_sheets: tuple[str, ...]
    cprs_ch_sheet: str
    program_name_cell: str
    annualized_volatility_column: str
    allocation_column: str
    start_row: int
    end_row: int


def get_mosers_all_programs_output_structure() -> MosersAllProgramsOutputStructure:
    """Return the output-structure contract used for All Programs workbook generation."""

    return MosersAllProgramsOutputStructure(
        required_sheets=_REQUIRED_SHEETS,
        cprs_ch_sheet=_TARGET_SHEET,
        program_name_cell=_PROGRAM_NAME_CELL,
        annualized_volatility_column=_VOL_COLUMN,
        allocation_column=_ALLOCATION_COLUMN,
        start_row=_START_ROW,
        end_row=_END_ROW,
    )


def generate_mosers_workbook(raw_nisa_path: str | Path) -> Workbook:
    """Generate a populated MOSERS workbook from raw NISA input.

    The internal MOSERS template workbook is loaded from package resources,
    parsed NISA values are written to fixed target cells/ranges, and the
    populated openpyxl workbook is returned without writing it to disk.
    """

    return _generate_mosers_workbook_from_parser(raw_nisa_path, parser=parse_nisa_all_programs)


def generate_mosers_workbook_ex_trend(raw_nisa_path: str | Path) -> Workbook:
    """Generate a populated MOSERS workbook from raw NISA Ex Trend input."""

    return _generate_mosers_workbook_from_parser(raw_nisa_path, parser=parse_nisa_ex_trend)


def generate_mosers_workbook_trend(raw_nisa_path: str | Path) -> Workbook:
    """Generate a populated MOSERS workbook from raw NISA Trend input."""

    return _generate_mosers_workbook_from_parser(raw_nisa_path, parser=parse_nisa_trend)


def _generate_mosers_workbook_from_parser(
    raw_nisa_path: str | Path,
    *,
    parser: Callable[[str | Path], NisaAllProgramsData],
) -> Workbook:
    parsed = parser(raw_nisa_path)
    workbook = load_mosers_template_workbook()
    structure = get_mosers_all_programs_output_structure()

    missing_sheets = [
        sheet for sheet in structure.required_sheets if sheet not in workbook.sheetnames
    ]
    if missing_sheets:
        missing = ", ".join(missing_sheets)
        raise ValueError(f"MOSERS template workbook missing required sheet(s): {missing}")

    worksheet = workbook[structure.cprs_ch_sheet]
    first_program = parsed.ch_rows[0].counterparty if parsed.ch_rows else ""
    worksheet[structure.program_name_cell] = first_program

    annualized_vols = [row.annualized_volatility for row in parsed.totals_rows]
    allocation_percentages = _build_allocation_percentages(parsed.totals_rows)

    _write_vertical_values(
        worksheet=worksheet,
        column_letter=structure.annualized_volatility_column,
        start_row=structure.start_row,
        end_row=structure.end_row,
        values=annualized_vols,
    )
    _write_vertical_values(
        worksheet=worksheet,
        column_letter=structure.allocation_column,
        start_row=structure.start_row,
        end_row=structure.end_row,
        values=allocation_percentages,
    )

    return workbook


def _build_allocation_percentages(totals_rows: tuple[NisaTotalsRow, ...]) -> list[float]:
    total_notional = sum(row.notional for row in totals_rows)
    if total_notional == 0:
        return [0.0 for _ in totals_rows]
    return [row.notional / total_notional for row in totals_rows]


def _write_vertical_values(
    *,
    worksheet: Worksheet,
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
