"""Tests for the NISA 'Exposure Maturity Schedule' parser (primary block)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest

from counter_risk.calculations.wal import calculate_wal
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


def _replace_total(path: Path, value: object, coordinate: str = "F15") -> None:
    """Persist a real cell value without changing the fixture's summary arithmetic."""
    workbook = openpyxl.load_workbook(path)
    try:
        workbook["Exposure Maturity Schedule"][coordinate] = value
        workbook.save(path)
    finally:
        workbook.close()


@pytest.mark.parametrize(
    "total",
    ["not-a-number", True, False, "NaN", "Infinity", "-Infinity", "1e309", "10%"],
)
@pytest.mark.parametrize("row", [14, 15, 17])
def test_invalid_nonblank_total_raises(tmp_path: Path, total: object, row: int) -> None:
    path = _write_schedule(tmp_path / "invalid-total.xlsx")
    # Keep a valid control in this named regression test so running it alone
    # proves that the production boundary accepts accounting amounts first.
    _replace_total(path, "$144.87", "F14")
    schedule = parse_exposure_maturity_schedule(path)
    assert [item.total for item in schedule.rows] == [144.87, 0.0, 156.06, 187.30]
    expected_wal = (39 * 144.87 + 53 * 156.06 + 67 * 187.30) / (144.87 + 156.06 + 187.30)
    assert calculate_wal(path, date(2025, 11, 30)) == pytest.approx(expected_wal)

    coordinate = f"F{row}"
    _replace_total(path, total, coordinate)

    with pytest.raises(ExposureMaturityScheduleError) as excinfo:
        parse_exposure_maturity_schedule(path)
    message = str(excinfo.value)
    assert "Exposure Maturity Schedule" in message
    assert f"row {row}" in message
    assert f"Total column 6 ({coordinate})" in message
    assert repr(total) in message
    assert isinstance(excinfo.value.__cause__, (ValueError, TypeError))

    # The public WAL boundary must propagate the parser error rather than return
    # a biased result after silently dropping this leg of an otherwise valid book.
    with pytest.raises(ExposureMaturityScheduleError, match="Total column 6"):
        calculate_wal(path, date(2025, 11, 30))


@pytest.mark.parametrize("total", [None, "", "   "])
def test_blank_totals_remain_zero(tmp_path: Path, total: object) -> None:
    path = _write_schedule(tmp_path / "blank-total.xlsx")
    expected_wal = calculate_wal(path, date(2025, 11, 30))
    _replace_total(path, total)

    schedule = parse_exposure_maturity_schedule(path)
    assert schedule.rows[1].total == 0.0
    assert calculate_wal(path, date(2025, 11, 30)) == pytest.approx(expected_wal)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("$1,234.50", 1234.5), ("(1,234.50)", -1234.5), ("0", 0.0), (12.5, 12.5)],
)
def test_valid_accounting_totals_preserve_amounts(
    tmp_path: Path, raw: object, expected: float
) -> None:
    path = _write_schedule(tmp_path / "accounting-total.xlsx")
    _replace_total(path, raw)
    assert parse_exposure_maturity_schedule(path).rows[1].total == expected


def test_valid_accounting_totals_reach_wal(tmp_path: Path) -> None:
    path = _write_schedule(
        tmp_path / "accounting-wal.xlsx",
        rows=((datetime(2025, 12, 30), 100.0), (datetime(2026, 1, 29), 300.0)),
    )
    _replace_total(path, "$100.00", "F14")
    _replace_total(path, "$300.00")
    assert calculate_wal(path, date(2025, 11, 30)) == pytest.approx(52.5)


def test_oversized_numeric_total_raises_with_cell_context(tmp_path: Path) -> None:
    path = _write_schedule(tmp_path / "oversized-total.xlsx")
    # Excel writers coerce integers to floats. Patch the actual numeric XML cell
    # so openpyxl reads the oversized integer a malformed workbook can contain.
    with ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    sheet = ElementTree.fromstring(entries["xl/worksheets/sheet1.xml"])
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    cell = sheet.find(".//s:c[@r='F14']/s:v", ns)
    assert cell is not None
    cell.text = str(10**400)
    entries["xl/worksheets/sheet1.xml"] = ElementTree.tostring(sheet)
    with ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    with pytest.raises(
        ExposureMaturityScheduleError, match=r"row 14, Total column 6 \(F14\)"
    ) as exc:
        parse_exposure_maturity_schedule(path)
    assert isinstance(exc.value.__cause__, OverflowError)
    with pytest.raises(ExposureMaturityScheduleError, match="Total column 6"):
        calculate_wal(path, date(2025, 11, 30))
