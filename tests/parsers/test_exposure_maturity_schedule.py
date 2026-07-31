"""Tests for the NISA 'Exposure Maturity Schedule' parser (primary block)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from counter_risk.parsers.exposure_maturity_schedule import (
    ExposureMaturityScheduleError,
    ExposureMaturityWorksheetMissingError,
    parse_exposure_maturity_schedule,
)

openpyxl = pytest.importorskip("openpyxl")
Workbook = openpyxl.Workbook


def _write_schedule(
    path: Path,
    *,
    block_label: str = "NISA TIPS",
    px: datetime = datetime(2025, 11, 30),
    rows: tuple[tuple[datetime, float | None], ...] = (
        (datetime(2026, 1, 8), 144.87),
        (datetime(2026, 1, 15), None),  # blank Total -> treated as 0
        (datetime(2026, 1, 22), 156.06),
        (datetime(2026, 2, 5), 187.30),
    ),
    sheet_name: str = "Exposure Maturity Schedule",
) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    # Px Date label + value (placed off to the right, as in the real files)
    ws.cell(row=4, column=7).value = "Px Date"
    ws.cell(row=4, column=8).value = px
    # Block label + header row: dates in col B(2), Total in col F(6)
    ws.cell(row=10, column=3).value = block_label
    ws.cell(row=11, column=3).value = "Reverse Repo"
    ws.cell(row=11, column=5).value = "Total Return Swaps"
    ws.cell(row=11, column=6).value = "Total"
    r = 14
    for mat, total in rows:
        ws.cell(row=r, column=2).value = mat
        if total is not None:
            ws.cell(row=r, column=6).value = total
        r += 1
    ws.cell(row=r, column=2).value = "Total"
    ws.cell(row=r, column=6).value = sum(t for _, t in rows if t)
    wb.save(path)
    return path


def test_parse_primary_block_px_date_and_rows(tmp_path: Path) -> None:
    p = _write_schedule(tmp_path / "sched.xlsx")
    schedule = parse_exposure_maturity_schedule(p)

    assert schedule.px_date == date(2025, 11, 30)
    assert schedule.block == "NISA TIPS"
    assert [(r.maturity_date, r.total) for r in schedule.rows] == [
        (date(2026, 1, 8), 144.87),
        (date(2026, 1, 15), 0.0),
        (date(2026, 1, 22), 156.06),
        (date(2026, 2, 5), 187.30),
    ]


def test_parse_returns_no_rows_when_tips_block_absent(tmp_path: Path) -> None:
    """WAL tracks the TIPS block only.

    Once TIPS is wound down the sheet carries only the replacement exposure (e.g.
    Synthetic US Treasuries), which must NOT be picked up: the schedule comes back
    empty so WAL reports 0 rather than silently switching to a different product.
    """
    p = _write_schedule(tmp_path / "syn.xlsx", block_label="NISA SYNTHETIC US TREASURIES")
    schedule = parse_exposure_maturity_schedule(p)

    assert schedule.block == ""
    assert schedule.rows == ()
    assert schedule.px_date == date(2025, 11, 30)


def test_missing_worksheet_raises(tmp_path: Path) -> None:
    wb = Workbook()
    wb.active.title = "Something Else"
    p = tmp_path / "nosheet.xlsx"
    wb.save(p)
    with pytest.raises(ExposureMaturityWorksheetMissingError):
        parse_exposure_maturity_schedule(p)


def test_no_maturity_rows_raises(tmp_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Exposure Maturity Schedule"
    ws.cell(row=10, column=3).value = "NISA TIPS"
    ws.cell(row=11, column=6).value = "Total"
    p = tmp_path / "empty.xlsx"
    wb.save(p)
    with pytest.raises(ExposureMaturityScheduleError):
        parse_exposure_maturity_schedule(p)
