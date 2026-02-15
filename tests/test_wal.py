"""Tests for weighted average life (WAL) calculations."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

from counter_risk.calculations.wal import calculate_wal


def test_calculate_wal_fixture_matches_expected_value() -> None:
    wal = calculate_wal(
        Path("tests/fixtures/nisa/NISA_Monthly_Exposure_Summary_sanitized.xlsx"),
        date(2025, 12, 31),
    )
    assert wal == pytest.approx(2.1369565217391304)


def test_calculate_wal_is_deterministic_for_same_inputs() -> None:
    fixture = Path("tests/fixtures/nisa/NISA_Monthly_Exposure_Summary_sanitized.xlsx")
    first = calculate_wal(fixture, "2025-12-31")
    second = calculate_wal(fixture, datetime(2025, 12, 31, 13, 45))
    assert first == second


def test_calculate_wal_missing_return_swaps_uses_all_rows(tmp_path: Path) -> None:
    workbook = _create_exposure_summary_workbook(
        tmp_path / "no_return_swaps.xlsx",
        rows=[
            ("Alpha", "Interest Rate Swap", 100.0, 1.0),
            ("Bravo", "Repo", 50.0, 4.0),
        ],
    )
    wal = calculate_wal(workbook, "2026-01-31")
    assert wal == pytest.approx(2.0)


def test_calculate_wal_returns_zero_when_all_rows_are_zero_filled(tmp_path: Path) -> None:
    workbook = _create_exposure_summary_workbook(
        tmp_path / "zeros.xlsx",
        rows=[
            ("Alpha", "Interest Rate Swap", None, 2.0),
            ("Bravo", "Repo", 0.0, None),
        ],
    )
    wal = calculate_wal(workbook, "2026-01-31")
    assert wal == 0.0


def test_calculate_wal_returns_zero_when_only_return_swaps_present(tmp_path: Path) -> None:
    workbook = _create_exposure_summary_workbook(
        tmp_path / "only_return_swaps.xlsx",
        rows=[
            ("Alpha", "Return Swaps", 1000.0, 3.0),
            ("Bravo", "Return Swap", 50.0, 1.0),
        ],
    )
    wal = calculate_wal(workbook, "2026-01-31")
    assert wal == 0.0


def test_calculate_wal_empty_data_raises_value_error(tmp_path: Path) -> None:
    workbook = _create_exposure_summary_workbook(tmp_path / "empty.xlsx", rows=[])
    with pytest.raises(ValueError, match="produced no rows"):
        calculate_wal(workbook, "2026-01-31")


def test_calculate_wal_invalid_px_date_raises_value_error(tmp_path: Path) -> None:
    workbook = _create_exposure_summary_workbook(
        tmp_path / "single_row.xlsx",
        rows=[("Alpha", "Repo", 100.0, 2.0)],
    )
    with pytest.raises(ValueError, match="ISO date string"):
        calculate_wal(workbook, "01-31-2026")


def _create_exposure_summary_workbook(path: Path, rows: list[tuple[Any, Any, Any, Any]]) -> Path:
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Exposure Maturity Summary"

    headers = (
        "Counterparty",
        "Product Type",
        "Current Exposure",
        "Years to Maturity",
        "Maturity Date",
        "Bucket",
    )
    for column_index, header in enumerate(headers, start=1):
        sheet.cell(row=1, column=column_index).value = header

    for row_index, (counterparty, product_type, exposure, years) in enumerate(rows, start=2):
        sheet.cell(row=row_index, column=1).value = counterparty
        sheet.cell(row=row_index, column=2).value = product_type
        sheet.cell(row=row_index, column=3).value = exposure
        sheet.cell(row=row_index, column=4).value = years
        sheet.cell(row=row_index, column=5).value = "2030-01-31"
        sheet.cell(row=row_index, column=6).value = "1-3Y"

    workbook.save(path)
    workbook.close()
    return path
