"""Parser for CPRS-FCM inputs from MOSERS summary workbooks.

This module extracts two normalized tables from the `CPRS - FCM` worksheet:
- Totals by counterparty/FCM
- Futures detail rows

The available section differs by workbook variant:
- All Programs: totals and futures detail are present
- Ex Trend: totals present, futures detail absent
- Trend: futures detail present, totals absent/minimal
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, TypedDict
from zipfile import BadZipFile, ZipFile

from counter_risk.normalize import canonicalize_name, safe_display_name
from counter_risk.parsers._variant_text import normalize_variant_text
from counter_risk.parsers._xlsx_reader import (
    resolve_sheet_target,
    load_shared_strings,
    read_sheet_rows,
    coerce_accounting_float,
)


class CprsFcmError(ValueError):
    """Base exception for CPRS-FCM parser errors."""


class CprsFcmColumnsMissingError(CprsFcmError):
    """Exception raised when required column headers are missing in the CPRS-FCM sheet."""

_XML_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

_FCM_SHEET_ALIASES = ("cprs - fcm", "futures - fcm", "cprs-fcm")
_TOTALS_SECTION_MARKER = "total by counterparty/ fcm"
_FUTURES_SECTION_MARKER = "futures detail"
_FUTURES_FOOTER_MARKER = "risk exclusive of the trend positions"

_TOTAL_COLUMNS: tuple[str, ...] = (
    "counterparty",
    "TIPS",
    "Treasury",
    "Equity",
    "Commodity",
    "Currency",
    "Notional",
    "NotionalChange",
)

_TOTAL_DTYPES: dict[str, str] = {
    "counterparty": "string",
    "TIPS": "float64",
    "Treasury": "float64",
    "Equity": "float64",
    "Commodity": "float64",
    "Currency": "float64",
    "Notional": "float64",
    "NotionalChange": "float64",
}

_FUTURES_COLUMNS: tuple[str, ...] = (
    "account",
    "description",
    "class",
    "fcm",
    "clearing_house",
    "notional",
)

_FUTURES_DTYPES: dict[str, str] = {
    "account": "string",
    "description": "string",
    "class": "string",
    "fcm": "string",
    "clearing_house": "string",
    "notional": "float64",
}


class FcmTotalEvidence(TypedDict):
    """Workbook source location for a parsed totals row."""

    counterparty: str
    sheet: str
    row: int
    method: str


def parse_fcm_totals(path: Path | str) -> Any:  # pandas.DataFrame
    """Parse totals-by-counterparty section from the CPRS-FCM worksheet."""
    return _to_dataframe(
        records=_parse_fcm_total_records(path), columns=_TOTAL_COLUMNS, dtypes=_TOTAL_DTYPES
    )


def parse_fcm_totals_with_evidence(
    path: Path | str,
) -> tuple[Any, dict[str, FcmTotalEvidence]]:  # pandas.DataFrame
    """Parse totals and evidence from one workbook read."""
    records = _parse_fcm_total_records(path)
    return (
        _to_dataframe(records=records, columns=_TOTAL_COLUMNS, dtypes=_TOTAL_DTYPES),
        _fcm_total_evidence_from_records(records),
    )


def parse_fcm_total_evidence(path: Path | str) -> dict[str, FcmTotalEvidence]:
    """Return source-location evidence keyed by parsed counterparty."""
    return _fcm_total_evidence_from_records(_parse_fcm_total_records(path))


def _fcm_total_evidence_from_records(
    records: list[dict[str, object]],
) -> dict[str, FcmTotalEvidence]:
    evidence: dict[str, FcmTotalEvidence] = {}
    for record in records:
        row = record["source_row"]
        evidence[str(record["counterparty"])] = {
            "counterparty": str(record["counterparty"]),
            "sheet": str(record["source_sheet"]),
            "row": row if isinstance(row, int) else int(str(row)),
            "method": "nisa_parser",
        }
    return evidence


def _parse_fcm_total_records(path: Path | str) -> list[dict[str, object]]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"CPRS-FCM file not found: {file_path}")

    try:
        sheet_name, rows = _read_fcm_sheet(file_path)
    except (KeyError, ET.ParseError, BadZipFile, ValueError) as exc:
        raise ValueError(f"Malformed CPRS-FCM workbook structure: {file_path}") from exc

    if _variant_for_path(file_path=file_path, sheet_name=sheet_name) == "trend":
        return []

    boundaries = _locate_totals_section(rows)
    if boundaries is None:
        return []

    start_row, end_row = boundaries
    header_row_number = _find_totals_header_row(rows)
    if header_row_number is None:
        raise CprsFcmColumnsMissingError("Unable to locate CPRS-FCM totals header row")
    column_map = _build_totals_column_map(rows, header_row_number)

    records: list[dict[str, object]] = []
    for row_number in range(start_row, end_row + 1):
        row = rows.get(row_number, {})
        counterparty = _normalize_text(row.get(column_map["counterparty"]))
        if not counterparty:
            continue

        lowered = counterparty.lower()
        if lowered in {"total", "subtotal"}:
            continue
        if _FUTURES_SECTION_MARKER in lowered:
            continue

        notional_value = _extract_numeric(row.get(column_map["Notional"]))
        category_values = [
            _extract_numeric(row.get(column_map[key]))
            for key in ("TIPS", "Treasury", "Equity", "Commodity", "Currency")
        ]
        if notional_value == 0.0 and all(value == 0.0 for value in category_values):
            continue

        records.append(
            {
                "counterparty": counterparty,
                "TIPS": _extract_numeric(row.get(column_map["TIPS"])),
                "Treasury": _extract_numeric(row.get(column_map["Treasury"])),
                "Equity": _extract_numeric(row.get(column_map["Equity"])),
                "Commodity": _extract_numeric(row.get(column_map["Commodity"])),
                "Currency": _extract_numeric(row.get(column_map["Currency"])),
                "Notional": notional_value,
                "NotionalChange": _extract_numeric(row.get(column_map["NotionalChange"])),
                "source_sheet": sheet_name,
                "source_row": row_number,
            }
        )

    return records


def parse_futures_detail(path: Path | str) -> Any:  # pandas.DataFrame
    """Parse futures detail section from the CPRS-FCM worksheet."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"CPRS-FCM file not found: {file_path}")

    try:
        sheet_name, rows = _read_fcm_sheet(file_path)
    except (KeyError, ET.ParseError, BadZipFile, ValueError) as exc:
        raise ValueError(f"Malformed CPRS-FCM workbook structure: {file_path}") from exc

    if _variant_for_path(file_path=file_path, sheet_name=sheet_name) == "ex_trend":
        return _to_dataframe(records=[], columns=_FUTURES_COLUMNS, dtypes=_FUTURES_DTYPES)

    boundaries = _locate_futures_detail_section(rows)
    if boundaries is None:
        return _to_dataframe(records=[], columns=_FUTURES_COLUMNS, dtypes=_FUTURES_DTYPES)

    start_row, end_row = boundaries
    header_row_number = start_row - 1
    column_map = _build_futures_column_map(rows, header_row_number)

    records: list[dict[str, object]] = []
    for row_number in range(start_row, end_row + 1):
        row = rows.get(row_number, {})
        account = _normalize_text(row.get(column_map["account"]))
        description = _normalize_text(row.get(column_map["description"]))
        position_class = _normalize_text(row.get(column_map["class"]))
        fcm = _normalize_text(row.get(column_map["fcm"]))
        clearing_house = _normalize_text(row.get(column_map["clearing_house"]))

        if not account and not description and not _normalize_text(row.get(column_map["notional"])):
            continue

        # Skip header-like rows if detected in malformed ranges.
        if account.lower() == "account" and description.lower() == "description":
            continue

        records.append(
            {
                "account": account,
                "description": description,
                "class": position_class,
                "fcm": fcm,
                "clearing_house": clearing_house,
                "notional": _extract_numeric(row.get(column_map["notional"])),
            }
        )

    return _to_dataframe(records=records, columns=_FUTURES_COLUMNS, dtypes=_FUTURES_DTYPES)


def _locate_totals_section(rows: dict[int, dict[int, str | None]]) -> tuple[int, int] | None:
    marker_row: int | None = None
    for row_number in sorted(rows):
        row = rows[row_number]
        row_texts = [_matching_key(val) for val in row.values() if val]
        if any(_TOTALS_SECTION_MARKER in t for t in row_texts):
            marker_row = row_number
            break

    if marker_row is None:
        return None

    start_row = marker_row + 1
    end_row = max(rows)
    for row_number in range(start_row, max(rows) + 1):
        row = rows.get(row_number, {})
        row_texts = [_matching_key(val) for val in row.values() if val]
        if any(_FUTURES_SECTION_MARKER in t or _FUTURES_FOOTER_MARKER in t for t in row_texts):
            end_row = row_number - 1
            break

    return start_row, max(start_row - 1, end_row)


def _locate_futures_detail_section(
    rows: dict[int, dict[int, str | None]],
) -> tuple[int, int] | None:
    marker_row: int | None = None
    for row_number in sorted(rows):
        row = rows[row_number]
        row_texts = [_matching_key(val) for val in row.values() if val]
        if any(_FUTURES_SECTION_MARKER in t for t in row_texts):
            marker_row = row_number
            break

    if marker_row is None:
        return None

    header_row = marker_row + 1
    start_row = header_row + 1
    end_row = max(rows)
    for row_number in range(start_row, max(rows) + 1):
        row = rows.get(row_number, {})
        row_texts = [_matching_key(val) for val in row.values() if val]
        if any(_FUTURES_FOOTER_MARKER in t for t in row_texts):
            end_row = row_number - 1
            break

    return start_row, max(start_row - 1, end_row)


def _variant_for_path(*, file_path: Path, sheet_name: str) -> str:
    title = normalize_variant_text(f"{file_path.name} {sheet_name}")
    if "ex trend" in title:
        return "ex_trend"
    if "trend" in title:
        return "trend"
    return "all_programs"


def _read_fcm_sheet(path: Path) -> tuple[str, dict[int, dict[int, str | None]]]:
    with ZipFile(path) as workbook_zip:
        try:
            selected_name, sheet_path = resolve_sheet_target(
                workbook_zip,
                lambda name: any(alias in _matching_key(name) for alias in _FCM_SHEET_ALIASES),
            )
        except ValueError as exc:
            raise ValueError("Unable to locate CPRS-FCM worksheet") from exc

        shared_strings = load_shared_strings(workbook_zip)
        sheet_xml = ET.fromstring(workbook_zip.read(sheet_path))
        rows = read_sheet_rows(sheet_xml, shared_strings)

    return selected_name, rows


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return safe_display_name(value.replace("\n", " "))


def _matching_key(value: str | None) -> str:
    return canonicalize_name(_normalize_text(value)).casefold()


def _extract_numeric(value: str | None) -> float:
    return coerce_accounting_float(value, strip_percent=True)


_TOTALS_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "counterparty": ("counterparty", "counterparty/ fcm", "counterparty/fcm", "fcm"),
    "TIPS": ("tips",),
    "Treasury": ("treasury",),
    "Equity": ("equity",),
    "Commodity": ("commodity",),
    "Currency": ("currency",),
    "Notional": ("notional", "total notional"),
    "NotionalChange": ("notional change from prior month", "notional change"),
}

_FUTURES_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "account": ("account",),
    "description": ("description",),
    "class": ("class",),
    "fcm": ("fcm",),
    "clearing_house": ("clearing house", "clearing_house"),
    "notional": ("notional",),
}


def _header_matches_alias(canonical_name: str, normalized_header: str, alias: str) -> bool:
    if canonical_name == "Notional":
        if normalized_header == alias:
            return True
        return normalized_header.endswith(alias) and "change" not in normalized_header
    return normalized_header == alias or alias in normalized_header


def _find_totals_header_row(rows: dict[int, dict[int, str | None]]) -> int | None:
    for row_number in sorted(rows):
        row = rows[row_number]
        for val in row.values():
            if val:
                norm = _matching_key(val)
                if (
                    "counterparty/" in norm
                    or "counterparty /" in norm
                    or ("counterparty" in norm and "fcm" in norm)
                ):
                    return row_number
    return None


def _build_totals_column_map(
    rows: dict[int, dict[int, str | None]], header_row_number: int
) -> dict[str, int]:
    header_row = rows.get(header_row_number, {})
    next_row = rows.get(header_row_number + 1, {})
    column_map: dict[str, int] = {}
    all_columns = sorted(set(header_row) | set(next_row))
    for column_index in all_columns:
        combined_header = " ".join(
            part
            for part in (
                _normalize_text(header_row.get(column_index)),
                _normalize_text(next_row.get(column_index)),
            )
            if part
        )
        combined_header = _matching_key(combined_header)
        normalized = combined_header
        if not normalized:
            continue

        for canonical_name, aliases in _TOTALS_COLUMN_ALIASES.items():
            if canonical_name in column_map:
                continue
            if any(_header_matches_alias(canonical_name, normalized, alias) for alias in aliases):
                column_map[canonical_name] = column_index
                break

    missing_headers = [col for col in _TOTALS_COLUMN_ALIASES if col not in column_map]
    if missing_headers:
        raise CprsFcmColumnsMissingError(
            f"Missing required columns in FCM totals: {', '.join(missing_headers)}"
        )

    return column_map


def _build_futures_column_map(
    rows: dict[int, dict[int, str | None]], header_row_number: int
) -> dict[str, int]:
    header_row = rows.get(header_row_number, {})
    column_map: dict[str, int] = {}
    for column_index, val in header_row.items():
        if not val:
            continue
        normalized = _matching_key(val)
        for canonical_name, aliases in _FUTURES_COLUMN_ALIASES.items():
            if canonical_name in column_map:
                continue
            if any(alias == normalized or alias in normalized for alias in aliases):
                column_map[canonical_name] = column_index
                break

    missing_headers = [col for col in _FUTURES_COLUMN_ALIASES if col not in column_map]
    if missing_headers:
        raise CprsFcmColumnsMissingError(
            f"Missing required columns in FCM futures detail: {', '.join(missing_headers)}"
        )

    return column_map


def _to_dataframe(
    *, records: list[dict[str, object]], columns: tuple[str, ...], dtypes: dict[str, str]
) -> Any:
    try:
        import pandas as pd
    except ModuleNotFoundError as exc:  # pragma: no cover - environment-dependent
        raise ModuleNotFoundError(
            "CPRS-FCM parser requires pandas to be installed in the runtime environment"
        ) from exc

    df = pd.DataFrame(records) if records else pd.DataFrame(columns=columns)

    for column in columns:
        if column not in df.columns:
            df[column] = 0.0 if dtypes[column] == "float64" else ""

    df = df.loc[:, list(columns)]
    return df.astype(dtypes)

