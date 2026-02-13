"""Historical workbook append helpers for Counter Risk chart-linked files.

This module centralizes shared workbook/date/header validation used by the
historical graph workbook update path. Variant-specific row append functions are
implemented in follow-on slices.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

SHEET_ALL_PROGRAMS_3_YEAR = "All Programs 3 Year"
SHEET_EX_LLC_3_YEAR = "ex LLC 3 Year"
SHEET_LLC_3_YEAR = "LLC 3 Year"

SERIES_BY_SHEET: dict[str, tuple[str, ...]] = {
    SHEET_ALL_PROGRAMS_3_YEAR: (
        "Total",
        "Total x-clearing",
        "Cash",
        "Class",
        "TIPS",
        "Nominal",
        "Equity",
        "Currency",
        "Commodity",
    ),
    SHEET_EX_LLC_3_YEAR: (
        "Total",
        "Class",
        "TIPS",
        "Nominal",
        "Equity",
        "Commodity",
        "Currency",
    ),
    SHEET_LLC_3_YEAR: (
        "Total",
        "Class",
        "Nominal",
        "Equity",
        "Commodity",
        "Currency",
    ),
}

DATE_HEADER_CANDIDATES: tuple[str, ...] = ("date", "as of date", "as-of date")


class HistoricalUpdateError(ValueError):
    """Base error for historical workbook update failures."""


class WorkbookValidationError(HistoricalUpdateError):
    """Raised when a workbook path or structure is invalid."""


class WorksheetNotFoundError(HistoricalUpdateError):
    """Raised when a required worksheet does not exist."""


class AppendDateError(HistoricalUpdateError):
    """Raised when append date resolution or ordering checks fail."""


def _as_path(value: str | Path, *, field_name: str) -> Path:
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value.strip():
        return Path(value)
    raise WorkbookValidationError(f"{field_name} must be a non-empty path-like value")


def _validate_workbook_path(path: Path, *, field_name: str = "workbook_path") -> None:
    if path.suffix.lower() != ".xlsx":
        raise WorkbookValidationError(f"{field_name} must point to an .xlsx file: {path}")
    if not path.exists():
        raise FileNotFoundError(f"Workbook not found: {path}")
    if not path.is_file():
        raise WorkbookValidationError(f"{field_name} must point to a file: {path}")


def _normalize_header(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).casefold()


def _find_header_row(
    worksheet: Any,
    *,
    max_scan_rows: int = 12,
    max_scan_cols: int = 40,
) -> int:
    upper_row = min(int(getattr(worksheet, "max_row", max_scan_rows)), max_scan_rows)
    upper_col = min(int(getattr(worksheet, "max_column", max_scan_cols)), max_scan_cols)

    for row_index in range(1, upper_row + 1):
        for col_index in range(1, upper_col + 1):
            header_value = _normalize_header(worksheet.cell(row=row_index, column=col_index).value)
            if header_value in DATE_HEADER_CANDIDATES:
                return row_index

    raise WorkbookValidationError(
        f"Unable to locate a header row containing a date label in worksheet {worksheet.title!r}"
    )


def _build_header_map(
    worksheet: Any,
    *,
    header_row: int,
    max_scan_cols: int = 256,
) -> dict[str, int]:
    upper_col = min(int(getattr(worksheet, "max_column", max_scan_cols)), max_scan_cols)
    header_map: dict[str, int] = {}
    for col_index in range(1, upper_col + 1):
        normalized = _normalize_header(worksheet.cell(row=header_row, column=col_index).value)
        if normalized:
            header_map[normalized] = col_index
    return header_map


def _resolve_append_date(*, append_date: date | None, config_as_of_date: date | None) -> date:
    resolved = append_date if append_date is not None else config_as_of_date
    if resolved is None:
        raise AppendDateError(
            "Append date is required. Provide append_date or config_as_of_date."
        )
    return resolved


def _coerce_rollup_data(rollup_data: Mapping[str, Any]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for raw_key, raw_value in rollup_data.items():
        key = _normalize_header(raw_key)
        if not key:
            continue
        try:
            numeric_value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise HistoricalUpdateError(f"Rollup value for {raw_key!r} must be numeric") from exc
        normalized[key] = numeric_value
    return normalized


def append_row_all_programs(
    workbook_path: str | Path,
    rollup_data: Mapping[str, Any],
    *,
    append_date: date | None = None,
    config_as_of_date: date | None = None,
) -> Path:
    """Append one row to the `All Programs 3 Year` worksheet."""

    del rollup_data
    del append_date
    del config_as_of_date
    raise NotImplementedError("append_row_all_programs is not implemented yet")


def append_row_ex_trend(
    workbook_path: str | Path,
    rollup_data: Mapping[str, Any],
    *,
    append_date: date | None = None,
    config_as_of_date: date | None = None,
) -> Path:
    """Append one row to the `ex LLC 3 Year` worksheet."""

    del rollup_data
    del append_date
    del config_as_of_date
    raise NotImplementedError("append_row_ex_trend is not implemented yet")


def append_row_trend(
    workbook_path: str | Path,
    rollup_data: Mapping[str, Any],
    *,
    append_date: date | None = None,
    config_as_of_date: date | None = None,
) -> Path:
    """Append one row to the `LLC 3 Year` worksheet."""

    del rollup_data
    del append_date
    del config_as_of_date
    raise NotImplementedError("append_row_trend is not implemented yet")


__all__ = [
    "AppendDateError",
    "HistoricalUpdateError",
    "SHEET_ALL_PROGRAMS_3_YEAR",
    "SHEET_EX_LLC_3_YEAR",
    "SHEET_LLC_3_YEAR",
    "SERIES_BY_SHEET",
    "WorkbookValidationError",
    "WorksheetNotFoundError",
    "append_row_all_programs",
    "append_row_ex_trend",
    "append_row_trend",
]
