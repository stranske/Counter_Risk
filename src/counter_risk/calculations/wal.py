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


def calculate_wal(exposure_summary_path: Path | str, px_date: date | datetime | str) -> float:
    """Calculate WAL (in days) from an exposure maturity summary workbook."""

    fallback_px = _coerce_px_date(px_date)
    schedule = parse_exposure_maturity_schedule(exposure_summary_path)
    px = schedule.px_date or fallback_px

    total_exposure = sum(row.total for row in schedule.rows)
    if not math.isfinite(total_exposure):
        raise ValueError("Total exposure is not finite")
    if total_exposure == 0:
        return 0.0

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
