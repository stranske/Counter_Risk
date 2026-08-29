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


# A long leg maturing in one year against an opposing short leg maturing in ten,
# sized so the signed sum survives as one hundredth of a currency unit out of a
# two-million gross book. Finite, so the isfinite guard passes; useless, because the
# quotient lands nine orders of magnitude outside the schedule's own maturity span.
_NEAR_CANCELLING_PX = datetime(2025, 11, 30)
_NEAR_CANCELLING_ROWS = (
    (datetime(2026, 11, 30), 1_000_000.00),  # 365 days
    (datetime(2035, 11, 30), -999_999.99),  # 3652 days
)


def test_wal_raises_on_near_cancelling_signed_denominator(tmp_path: Path) -> None:
    p = _write_schedule(
        tmp_path / "near_cancelling.xlsx",
        px=_NEAR_CANCELLING_PX,
        rows=_NEAR_CANCELLING_ROWS,
    )
    with pytest.raises(ValueError) as excinfo:
        calculate_wal(p, _NEAR_CANCELLING_PX.date())
    message = str(excinfo.value)
    # The refusal has to name both totals, or the operator cannot tell a hedged book
    # from a corrupt one.
    assert "0.01" in message, message
    assert "1999999.99" in message, message


def test_wal_result_lies_within_the_schedule_maturity_span(tmp_path: Path) -> None:
    # WAL is an exposure-weighted average of the row offsets, so every value this
    # function returns must sit between the earliest and latest of them. A schedule
    # that cannot honour that must raise instead of returning something.
    px = _NEAR_CANCELLING_PX
    schedules = {
        "all_long": (
            (datetime(2026, 11, 30), 1_000_000.00),
            (datetime(2035, 11, 30), 250_000.00),
        ),
        "near_cancelling": _NEAR_CANCELLING_ROWS,
    }
    returned_a_value = False
    for name, rows in schedules.items():
        p = _write_schedule(tmp_path / f"span_{name}.xlsx", px=px, rows=rows)
        offsets = [(maturity.date() - px.date()).days for maturity, _ in rows]
        low, high = min(offsets), max(offsets)
        try:
            wal = calculate_wal(p, px.date())
        except ValueError:
            continue
        returned_a_value = True
        message = f"WAL {wal:,.0f} days is outside the span [{low}, {high}] for schedule {name!r}"
        assert low <= wal <= high, message
    assert returned_a_value, "no schedule returned a value; the span invariant was never exercised"


def test_wal_raises_when_mixed_sign_result_escapes_maturity_span(tmp_path: Path) -> None:
    # This is not close enough to flat for the relative denominator guard: the
    # signed total is roughly 82% of gross exposure. It still produces a negative
    # signed-weighted WAL, below the earliest one-year maturity, so the result is
    # not a valid weighted average and must be rejected.
    px = _NEAR_CANCELLING_PX
    p = _write_schedule(
        tmp_path / "out_of_span_mixed_sign.xlsx",
        px=px,
        rows=(
            (datetime(2026, 11, 30), 1_000_000.00),
            (datetime(2035, 11, 30), -100_000.00),
        ),
    )
    with pytest.raises(ValueError, match="outside the schedule maturity span") as excinfo:
        calculate_wal(p, px.date())
    assert "signed total 900000.0" in str(excinfo.value)
    assert "gross magnitude 1100000.0" in str(excinfo.value)


def test_wal_returns_zero_only_for_empty_gross_exposure(tmp_path: Path) -> None:
    # The wound-down book: the TIPS block is still on the sheet but carries no
    # exposure. Gross magnitude is zero, so 0.0 is the honest answer. (The parser
    # rejects a block with no maturity rows at all, so an all-zero block is the
    # rowless case as it actually reaches this function.)
    wound_down = _write_schedule(
        tmp_path / "wound_down.xlsx",
        px=_NEAR_CANCELLING_PX,
        rows=(
            (datetime(2026, 11, 30), 0.0),
            (datetime(2035, 11, 30), 0.0),
        ),
    )
    assert calculate_wal(wound_down, _NEAR_CANCELLING_PX.date()) == 0.0

    # The hedged book: legs cancel to exactly zero, but two million of gross exposure
    # is present. Returning 0.0 here would make it indistinguishable from the above.
    hedged = _write_schedule(
        tmp_path / "hedged_flat.xlsx",
        px=_NEAR_CANCELLING_PX,
        rows=(
            (datetime(2026, 11, 30), 1_000_000.00),
            (datetime(2035, 11, 30), -1_000_000.00),
        ),
    )
    with pytest.raises(ValueError):
        calculate_wal(hedged, _NEAR_CANCELLING_PX.date())
