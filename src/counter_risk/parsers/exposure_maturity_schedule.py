"""Parser for exposure maturity summary workbooks used by WAL calculations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

_TARGET_SHEET_NAME = "Exposure Maturity Summary"
_REQUIRED_HEADERS: tuple[str, ...] = (
    "counterparty",
    "product type",
    "current exposure",
    "years to maturity",
)


class ExposureMaturityScheduleError(ValueError):
    """Base error for exposure maturity schedule parsing failures."""


class ExposureMaturityWorkbookLoadError(ExposureMaturityScheduleError):
    """Raised when the workbook cannot be opened/loaded."""


class ExposureMaturityWorksheetMissingError(ExposureMaturityScheduleError):
    """Raised when the required worksheet is missing."""


class ExposureMaturityColumnsMissingError(ExposureMaturityScheduleError):
    """Raised when required columns cannot be found within the scan range."""


@dataclass(frozen=True)
class ExposureMaturityRow:
    """Normalized row from an exposure maturity summary sheet."""

    counterparty: str
    product_type: str
    current_exposure: float
    years_to_maturity: float


def parse_exposure_maturity_schedule(path: Path | str) -> tuple[ExposureMaturityRow, ...]:
    """Parse the exposure maturity schedule rows needed for WAL calculation."""

    workbook_path = Path(path)
    if not workbook_path.exists():
        raise FileNotFoundError(f"Exposure maturity workbook not found: {workbook_path}")
    if workbook_path.suffix.lower() != ".xlsx":
        raise ValueError(f"Exposure maturity workbook must be an .xlsx file: {workbook_path}")

    try:
        from openpyxl import load_workbook  # type: ignore[import-untyped]
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("openpyxl is required to parse exposure maturity workbooks") from exc

    try:
        from openpyxl.utils.exceptions import InvalidFileException  # type: ignore[import-untyped]

        invalid_file_exception = InvalidFileException
    except ModuleNotFoundError:  # pragma: no cover - environment dependent
        invalid_file_exception = ValueError

    try:
        workbook = load_workbook(filename=workbook_path, read_only=True, data_only=True)
    except (OSError, BadZipFile, invalid_file_exception, ValueError, TypeError) as exc:
        raise ExposureMaturityWorkbookLoadError(
            f"Unable to open exposure maturity workbook: {workbook_path}"
        ) from exc

    try:
        if _TARGET_SHEET_NAME not in workbook.sheetnames:
            raise ExposureMaturityWorksheetMissingError(
                f"Missing required worksheet {_TARGET_SHEET_NAME!r} in workbook: {workbook_path}"
            )
        worksheet = workbook[_TARGET_SHEET_NAME]
        header_row, header_map = _find_header_row_and_map(worksheet)
        rows = _parse_rows(worksheet=worksheet, header_row=header_row, header_map=header_map)
    finally:
        workbook.close()

    if not rows:
        raise ValueError("Exposure maturity workbook parser produced no rows")
    return tuple(rows)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _coerce_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    text = _normalize_text(value)
    if not text or text in {"-", "--", "N/A", "n/a"}:
        return 0.0
    if text.startswith("(") and text.endswith(")"):
        text = f"-{text[1:-1]}"

    cleaned = text.replace(",", "").replace("$", "")
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"Unable to parse numeric cell value: {value!r}") from exc


def _build_header_map(worksheet: Any, *, header_row: int) -> dict[str, int]:
    header_map: dict[str, int] = {}
    max_column = int(worksheet.max_column)
    for column in range(1, max_column + 1):
        key = _normalize_text(worksheet.cell(row=header_row, column=column).value).casefold()
        if key:
            header_map[key] = column
    return header_map


def _find_header_row_and_map(
    worksheet: Any, *, max_scan_rows: int = 50
) -> tuple[int, dict[str, int]]:
    max_row = min(int(getattr(worksheet, "max_row", 0) or 0), max_scan_rows)
    best_missing: tuple[str, ...] = _REQUIRED_HEADERS
    for row_index in range(1, max_row + 1):
        header_map = _build_header_map(worksheet, header_row=row_index)
        missing = tuple(header for header in _REQUIRED_HEADERS if header not in header_map)
        if not missing:
            return row_index, header_map
        if len(missing) < len(best_missing):
            best_missing = missing

    missing_text = ", ".join(best_missing)
    raise ExposureMaturityColumnsMissingError(
        "Missing required headers in exposure maturity worksheet within scan range: "
        f"{missing_text}"
    )


def _parse_rows(
    *, worksheet: Any, header_row: int, header_map: dict[str, int]
) -> list[ExposureMaturityRow]:
    parsed: list[ExposureMaturityRow] = []
    max_row = int(worksheet.max_row)
    for row_number in range(header_row + 1, max_row + 1):
        counterparty = _normalize_text(
            worksheet.cell(row=row_number, column=header_map["counterparty"]).value
        )
        product_type = _normalize_text(
            worksheet.cell(row=row_number, column=header_map["product type"]).value
        )
        current_exposure_raw = worksheet.cell(
            row=row_number, column=header_map["current exposure"]
        ).value
        years_to_maturity_raw = worksheet.cell(
            row=row_number, column=header_map["years to maturity"]
        ).value

        if (
            not counterparty
            and not product_type
            and current_exposure_raw is None
            and years_to_maturity_raw is None
        ):
            continue

        parsed.append(
            ExposureMaturityRow(
                counterparty=counterparty,
                product_type=product_type,
                current_exposure=_coerce_float(current_exposure_raw),
                years_to_maturity=_coerce_float(years_to_maturity_raw),
            )
        )

    return parsed
