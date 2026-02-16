"""Weighted average life (WAL) calculations for exposure maturity inputs."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from counter_risk.parsers.exposure_maturity_schedule import (
    ExposureMaturityRow,
    parse_exposure_maturity_schedule,
)

_RETURN_SWAP_LABELS = {"return swap", "return swaps"}


def calculate_wal(exposure_summary_path: Path | str, px_date: date | datetime | str) -> float:
    """Calculate WAL from an exposure maturity summary workbook.

    Manual procedure mirrored by this function:
    1) Treat missing numeric values as zero (handled by parser coercion).
    2) Remove return swaps rows from the schedule.
    3) Compute weighted average life as:
       sum(current_exposure * years_to_maturity) / sum(current_exposure)
    """

    px_date = _coerce_px_date(px_date)
    rows = parse_exposure_maturity_schedule(exposure_summary_path)
    filtered_rows = [row for row in rows if not _is_return_swap(row)]

    total_exposure = sum(row.current_exposure for row in filtered_rows)
    if total_exposure == 0:
        return 0.0

    weighted_maturity = sum(row.current_exposure * row.years_to_maturity for row in filtered_rows)
    return weighted_maturity / total_exposure


def _is_return_swap(row: ExposureMaturityRow) -> bool:
    return _normalize_text(row.product_type) in _RETURN_SWAP_LABELS


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).casefold().strip()


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
