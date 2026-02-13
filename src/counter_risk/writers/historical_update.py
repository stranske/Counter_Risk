"""Historical workbook append helpers for Counter Risk chart-linked files.

This module centralizes shared workbook/date/header validation used by the
historical graph workbook update path. Variant-specific row append functions are
implemented in follow-on slices.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import date, datetime
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


def _get_date_column(header_map: Mapping[str, int]) -> int:
    for candidate in DATE_HEADER_CANDIDATES:
        column = header_map.get(candidate)
        if column is not None:
            return column
    raise WorkbookValidationError("Worksheet header row is missing a date column")


def _coerce_cell_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
            try:
                return datetime.strptime(stripped, fmt).date()
            except ValueError:
                continue
    raise AppendDateError(f"Unable to parse existing worksheet date value: {value!r}")


def _find_last_dated_row(worksheet: Any, *, header_row: int, date_column: int) -> int | None:
    max_row = int(getattr(worksheet, "max_row", header_row))
    for row_index in range(max_row, header_row, -1):
        raw_date = worksheet.cell(row=row_index, column=date_column).value
        parsed = _coerce_cell_date(raw_date)
        if parsed is not None:
            return row_index
    return None


def _append_to_sheet(
    *,
    workbook: Any,
    sheet_name: str,
    rollup_data: Mapping[str, Any],
    resolved_date: date,
) -> None:
    if sheet_name not in getattr(workbook, "sheetnames", []):
        raise WorksheetNotFoundError(f"Required worksheet not found: {sheet_name}")

    worksheet = workbook[sheet_name]
    header_row = _find_header_row(worksheet)
    header_map = _build_header_map(worksheet, header_row=header_row)
    date_column = _get_date_column(header_map)

    last_row = _find_last_dated_row(worksheet, header_row=header_row, date_column=date_column)
    if last_row is None:
        target_row = header_row + 1
    else:
        last_date = _coerce_cell_date(worksheet.cell(row=last_row, column=date_column).value)
        if last_date is None:
            raise AppendDateError(
                f"Last worksheet date is blank for sheet {sheet_name!r} at row {last_row}"
            )
        if resolved_date <= last_date:
            raise AppendDateError(
                "Append date must be newer than the last row date: "
                f"append_date={resolved_date.isoformat()} last_row_date={last_date.isoformat()}"
            )
        target_row = last_row + 1

    worksheet.cell(row=target_row, column=date_column).value = resolved_date

    normalized_rollups = _coerce_rollup_data(rollup_data)
    for series_name in SERIES_BY_SHEET[sheet_name]:
        normalized_series = _normalize_header(series_name)
        series_column = header_map.get(normalized_series)
        if series_column is None:
            LOGGER.warning(
                "Missing expected series header in %s: %s",
                sheet_name,
                series_name,
            )
            continue
        worksheet.cell(row=target_row, column=series_column).value = normalized_rollups.get(
            normalized_series,
            0.0,
        )


def _append_row(
    *,
    workbook_path: str | Path,
    sheet_name: str,
    rollup_data: Mapping[str, Any],
    append_date: date | None,
    config_as_of_date: date | None,
) -> Path:
    path = _as_path(workbook_path, field_name="workbook_path")
    _validate_workbook_path(path)
    resolved_date = _resolve_append_date(append_date=append_date, config_as_of_date=config_as_of_date)

    try:
        from openpyxl import load_workbook  # type: ignore[import-untyped]
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "openpyxl is required to update historical workbooks. "
            "Install project dev dependencies to enable this feature."
        ) from exc

    try:
        workbook = load_workbook(filename=path)
    except Exception as exc:
        raise WorkbookValidationError(f"Unable to load workbook: {path}") from exc

    try:
        _append_to_sheet(
            workbook=workbook,
            sheet_name=sheet_name,
            rollup_data=rollup_data,
            resolved_date=resolved_date,
        )
        workbook.save(path)
    finally:
        workbook.close()
    return path


def append_row_all_programs(
    workbook_path: str | Path,
    rollup_data: Mapping[str, Any],
    *,
    append_date: date | None = None,
    config_as_of_date: date | None = None,
) -> Path:
    """Append one row to the `All Programs 3 Year` worksheet."""
    return _append_row(
        workbook_path=workbook_path,
        sheet_name=SHEET_ALL_PROGRAMS_3_YEAR,
        rollup_data=rollup_data,
        append_date=append_date,
        config_as_of_date=config_as_of_date,
    )


def append_row_ex_trend(
    workbook_path: str | Path,
    rollup_data: Mapping[str, Any],
    *,
    append_date: date | None = None,
    config_as_of_date: date | None = None,
) -> Path:
    """Append one row to the `ex LLC 3 Year` worksheet."""
    return _append_row(
        workbook_path=workbook_path,
        sheet_name=SHEET_EX_LLC_3_YEAR,
        rollup_data=rollup_data,
        append_date=append_date,
        config_as_of_date=config_as_of_date,
    )


def append_row_trend(
    workbook_path: str | Path,
    rollup_data: Mapping[str, Any],
    *,
    append_date: date | None = None,
    config_as_of_date: date | None = None,
) -> Path:
    """Append one row to the `LLC 3 Year` worksheet."""
    return _append_row(
        workbook_path=workbook_path,
        sheet_name=SHEET_LLC_3_YEAR,
        rollup_data=rollup_data,
        append_date=append_date,
        config_as_of_date=config_as_of_date,
    )


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
