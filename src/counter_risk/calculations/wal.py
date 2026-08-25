"""Weighted average life (WAL) calculations for exposure maturity inputs.

WAL is the exposure-weighted average time-to-maturity of the **TIPS** block of the
NISA "Exposure Maturity Schedule", expressed in **days** from the Px Date:

    WAL = sum((maturity_date - px_date).days * total) / sum(total)

This mirrors the manual procedure ("((Beginning Dates - PxDate) * Total) /
Grand Total, summed").

TIPS-only, by design: the 2026 allocation change wound TIPS down and eliminated it
at end-June 2026 (Synthetic US Treasuries grew in as its replacement). Per the
process owner, WAL continues to track the TIPS block ONLY -- the replacement
Treasury exposure is NOT included. Once the TIPS block is gone from the NISA sheet
there is no TIPS exposure to measure, so WAL is 0 (the parser returns no rows and
this function returns 0.0). That is the expected value for June 2026 onward, not a
data error.

A return of 0.0 therefore means **no gross exposure**: every row total is zero, or
there are no rows at all. It does NOT mean "the book nets to flat". A hedged-to-flat
book -- one whose long and short legs cancel, exactly or nearly -- has real gross
exposure and no meaningful weighted average life, so it RAISES ValueError rather
than returning zero. Reporting 0.0 there would make a wound-down book and a hedged
book indistinguishable in the output, and the report carries no other signal that
the book was hedged.

The denominator is a SIGNED sum, so a mixed-sign schedule can cancel down to a
value near zero while remaining perfectly finite. Dividing by it produces an answer
many orders of magnitude outside the schedule's own maturity span (a correct WAL is
an exposure-weighted average of the row offsets, so it must lie between the earliest
and latest of them). The guard below compares the signed total against the gross
magnitude and refuses when the ratio falls below
``_NEAR_CANCELLATION_RELATIVE_TOLERANCE``.

NOTE: for months where TIPS is present, this deterministic method reproduces the
historical hand-entered WAL values to within ~0.5 day but not exactly; the sub-day
residual is not recoverable from the NISA source files and is left for the process
owner to confirm/adjust.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from pathlib import Path

from counter_risk.parsers.exposure_maturity_schedule import parse_exposure_maturity_schedule

#: Smallest ratio of |signed total| to gross magnitude that still yields a usable
#: denominator. A relative tolerance rather than an absolute epsilon because notional
#: magnitudes in this book span several orders of magnitude, so any fixed epsilon is
#: either meaningless at the top of that range or trigger-happy at the bottom. Below
#: 1e-6 the surviving net is under one part per million of the exposure that produced
#: it: float64 cancellation has consumed most of the significant digits, and the
#: quotient is no longer bounded by the schedule's own maturity span in any useful way.
_NEAR_CANCELLATION_RELATIVE_TOLERANCE = 1e-6


def calculate_wal(exposure_summary_path: Path | str, px_date: date | datetime | str) -> float:
    """Calculate WAL (in days) from an exposure maturity summary workbook.

    Returns 0.0 only when the schedule carries no gross exposure. Raises ValueError
    when the signed total nets to a negligible fraction of the gross magnitude, which
    is a hedged-to-flat book rather than an absent one.
    """

    fallback_px = _coerce_px_date(px_date)
    schedule = parse_exposure_maturity_schedule(exposure_summary_path)
    px = schedule.px_date or fallback_px

    total_exposure = sum(row.total for row in schedule.rows)
    gross_exposure = sum(abs(row.total) for row in schedule.rows)
    if not math.isfinite(total_exposure):
        raise ValueError("Total exposure is not finite")
    if gross_exposure == 0:
        return 0.0
    if abs(total_exposure) < _NEAR_CANCELLATION_RELATIVE_TOLERANCE * gross_exposure:
        raise ValueError(
            "Signed total exposure nets to a negligible fraction of gross exposure: "
            f"signed total {total_exposure!r}, gross magnitude {gross_exposure!r} "
            f"(ratio {abs(total_exposure) / gross_exposure:.3e} is below the "
            f"{_NEAR_CANCELLATION_RELATIVE_TOLERANCE:.0e} relative tolerance). "
            "This schedule is hedged to flat and has no meaningful weighted average "
            "life; dividing by the residual would report a value far outside the "
            "schedule's own maturity span."
        )

    weighted_days = sum((row.maturity_date - px).days * row.total for row in schedule.rows)
    return weighted_days / total_exposure


def _coerce_px_date(px_date: date | datetime | str) -> date:
    if isinstance(px_date, datetime):
        return px_date.date()
    if isinstance(px_date, date):
        return px_date
    if isinstance(px_date, str):
        try:
            return date.fromisoformat(px_date.strip())
        except ValueError as exc:
            raise ValueError(f"px_date must be an ISO date string, got: {px_date!r}") from exc
    raise TypeError(f"px_date must be date, datetime, or str; got {type(px_date).__name__}")
