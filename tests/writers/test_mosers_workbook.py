"""Tests for MOSERS workbook generation from raw NISA input."""

from __future__ import annotations

from datetime import date
import math
from pathlib import Path
import re
from collections.abc import Sequence
from typing import Any

from counter_risk.parsers import parse_cprs_ch, parse_fcm_totals, parse_futures_detail
from counter_risk.writers.mosers_workbook import generate_mosers_workbook

_A1_REF_PATTERN = re.compile(r"^([A-Z]+)(\d+)$")


def test_generate_mosers_workbook_creates_new_file_with_required_sheets(tmp_path: Path) -> None:
    destination = tmp_path / "MOSERS Generated - All Programs.xlsx"
    output_path = generate_mosers_workbook(
        raw_nisa_path=Path("tests/fixtures/NISA Monthly All Programs - Raw.xlsx"),
        output_path=destination,
    )

    assert output_path == destination
    assert output_path.exists()

    from openpyxl import load_workbook  # type: ignore[import-untyped]

    workbook = load_workbook(output_path, read_only=True, data_only=True)
    try:
        assert workbook.sheetnames == ["CPRS - CH", "CPRS - FCM"]
    finally:
        workbook.close()


def test_generate_mosers_workbook_output_is_parseable_by_existing_milestone_one_parsers(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "MOSERS Generated - All Programs.xlsx"
    output_path = generate_mosers_workbook(
        raw_nisa_path=Path("tests/fixtures/NISA Monthly All Programs - Raw.xlsx"),
        output_path=destination,
    )

    ch_df = parse_cprs_ch(output_path)
    totals_df = parse_fcm_totals(output_path)
    futures_df = parse_futures_detail(output_path)

    assert not ch_df.empty
    assert not totals_df.empty
    assert tuple(totals_df.columns) == (
        "counterparty",
        "TIPS",
        "Treasury",
        "Equity",
        "Commodity",
        "Currency",
        "Notional",
        "NotionalChange",
    )
    assert tuple(futures_df.columns) == (
        "account",
        "description",
        "class",
        "fcm",
        "clearing_house",
        "notional",
    )


def _sheet_grid(sheet: Any, *, width: int) -> tuple[tuple[Any, ...], ...]:
    rows: list[tuple[Any, ...]] = []
    for row_index in range(1, int(sheet.max_row) + 1):
        rows.append(
            tuple(sheet.cell(row=row_index, column=column).value for column in range(1, width + 1))
        )
    return tuple(rows)


def _column_to_index(column_label: str) -> int:
    index = 0
    for character in column_label:
        index = (index * 26) + (ord(character) - ord("A") + 1)
    return index


def _parse_a1(reference: str) -> tuple[int, int]:
    match = _A1_REF_PATTERN.match(reference.upper())
    if match is None:
        raise ValueError(f"Invalid A1 reference: {reference}")
    column_label, row_label = match.groups()
    return int(row_label), _column_to_index(column_label)


def _extract_range_values(
    grid: Sequence[Sequence[Any]], range_ref: str
) -> tuple[tuple[Any, ...], ...]:
    start_ref, end_ref = range_ref.replace("$", "").upper().split(":")
    start_row, start_col = _parse_a1(start_ref)
    end_row, end_col = _parse_a1(end_ref)
    min_row, max_row = sorted((start_row, end_row))
    min_col, max_col = sorted((start_col, end_col))

    rows: list[tuple[Any, ...]] = []
    for row_index in range(min_row, max_row + 1):
        rows.append(tuple(grid[row_index - 1][min_col - 1 : max_col]))
    return tuple(rows)


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _float_tolerant_equal(left: Any, right: Any) -> bool:
    if _is_sequence(left) and _is_sequence(right):
        if len(left) != len(right):
            return False
        return all(
            _float_tolerant_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )

    if isinstance(left, float) or isinstance(right, float):
        try:
            return math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-9)
        except (TypeError, ValueError):
            return False

    return bool(left == right)


def test_generate_mosers_workbook_matches_approved_reference_ranges(tmp_path: Path) -> None:
    destination = tmp_path / "MOSERS Generated - All Programs.xlsx"
    output_path = generate_mosers_workbook(
        raw_nisa_path=Path("tests/fixtures/NISA Monthly All Programs - Raw.xlsx"),
        output_path=destination,
        as_of_date=date(2025, 12, 31),
    )
    reference_path = Path("tests/fixtures/MOSERS Generated Reference - All Programs.xlsx")

    from openpyxl import load_workbook  # type: ignore[import-untyped]

    output_workbook = load_workbook(output_path, read_only=True, data_only=True)
    reference_workbook = load_workbook(reference_path, read_only=True, data_only=True)
    try:
        for sheet_name, width, ranges in (
            ("CPRS - CH", 11, ("A1:K3", "A5:K32")),
            ("CPRS - FCM", 14, ("A1:N6", "C7:N22", "C24:L26")),
        ):
            output_grid = _sheet_grid(output_workbook[sheet_name], width=width)
            reference_grid = _sheet_grid(reference_workbook[sheet_name], width=width)
            for range_ref in ranges:
                output_values = _extract_range_values(output_grid, range_ref)
                reference_values = _extract_range_values(reference_grid, range_ref)
                assert _float_tolerant_equal(
                    output_values, reference_values
                ), f"Workbook mismatch in {sheet_name} range {range_ref}"
    finally:
        output_workbook.close()
        reference_workbook.close()
