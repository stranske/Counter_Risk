"""Tests for weighted average life (WAL) calculations."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from counter_risk.calculations.wal import calculate_wal

openpyxl = pytest.importorskip("openpyxl")
Workbook = openpyxl.Workbook


def _write_schedule(
    path: Path,
    *,
    px: datetime = datetime(2025, 11, 30),
    rows: tuple[tuple[datetime, float | None], ...] = (
        (datetime(2025, 12, 30), 100.0),  # 30 days
        (datetime(2026, 1, 29), 300.0),  # 60 days
    ),
) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Exposure Maturity Schedule"
    ws.cell(row=4, column=7).value = "Px Date"
    ws.cell(row=4, column=8).value = px
    ws.cell(row=10, column=3).value = "NISA TIPS"
    ws.cell(row=11, column=6).value = "Total"
    r = 14
    for mat, total in rows:
        ws.cell(row=r, column=2).value = mat
        if total is not None:
            ws.cell(row=r, column=6).value = total
        r += 1
    ws.cell(row=r, column=2).value = "Total"
    wb.save(path)
    return path


def test_calculate_wal_weighted_days(tmp_path: Path) -> None:
    # (30*100 + 60*300) / (100+300) = (3000 + 18000)/400 = 52.5 days
    p = _write_schedule(tmp_path / "wal.xlsx")
    assert calculate_wal(p, date(2025, 11, 30)) == pytest.approx(52.5)


def test_calculate_wal_uses_sheet_px_date_over_argument(tmp_path: Path) -> None:
    # Sheet Px Date (2025-11-30) should be used even if a different arg is passed.
    p = _write_schedule(tmp_path / "wal2.xlsx")
    from_arg = calculate_wal(p, date(2020, 1, 1))
    assert from_arg == pytest.approx(52.5)


def test_calculate_wal_zero_when_all_totals_zero(tmp_path: Path) -> None:
    p = _write_schedule(
        tmp_path / "zero.xlsx",
        rows=((datetime(2025, 12, 30), 0.0), (datetime(2026, 1, 29), 0.0)),
    )
    assert calculate_wal(p, date(2025, 11, 30)) == 0.0


def test_calculate_wal_is_deterministic(tmp_path: Path) -> None:
    p = _write_schedule(tmp_path / "det.xlsx")
    assert calculate_wal(p, date(2025, 11, 30)) == calculate_wal(p, date(2025, 11, 30))
