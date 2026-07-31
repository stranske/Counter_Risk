"""Parser for CPRS-CH inputs from NISA drop-in workbooks."""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from zipfile import BadZipFile, ZipFile

from counter_risk.normalize import canonicalize_name, safe_display_name
from counter_risk.parsers._variant_text import normalize_variant_text
from counter_risk.parsers._xlsx_reader import (
    coerce_accounting_float,
    load_shared_strings,
    read_sheet_rows,
    resolve_sheet_target,
)

if TYPE_CHECKING:
    import pandas as pd

_XML_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

_CH_SHEET_ALIASES = ("cprs - ch", "cprs-ch")

_EXPECTED_SEGMENT_PATTERNS: dict[str, tuple[str, ...]] = {
    "swaps": ("swaps",),
    "repo": ("repo",),
    "futures": ("futures",),
    "futures_cdx": ("futures cdx", "futures/cdx", "futures / cdx", "futures-cdx"),
}

# The consolidated "Total by Counterparty/Clearing House" section re-lists every
# counterparty/clearing-house already seen in the segments above with the same
# values (it is a display rollup, not new data). Its label carries a variable
# trailing parenthetical (e.g. "...(This is not the legal obligation exposure)"),
# so it is matched by prefix rather than exact equality like the other segments.
# Deliberately the *full* phrase including "/clearing house": some real exports
# also stamp a shorter "Total by Counterparty" tag in column A of every data row
# within this section (a leftover formatting/grouping artifact) — matching only
# the longer phrase avoids misidentifying those data rows as new segment starts.
_TOTALS_SEGMENT_LABEL_PREFIX = "total by counterparty/clearing house"
_TOTALS_SEGMENT_TYPE = "totals"

# Footer/annotation rows that follow the totals section in real MOSERS exports and
# are not counterparty data (e.g. "MOSERS Program", "Notional Breakdown", asterisked
# footnotes) — must not be parsed as counterparty rows.
_FOOTER_ROW_PREFIXES = (
    "total",  # also catches legacy "Total"/"Subtotal" exact rows below
    "subtotal",
    "mosers program",
    "notional breakdown",
    "risk exclusive",
    "risk includes",
    "trend program",  # Trend-variant summary rows, not a real clearing-house row
    "*",  # footnote markers, e.g. "*Absolute value of notional shown..."
)

_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "Counterparty": ("counterparty", "counterparty/ clearing house", "clearing house"),
    "Cash": ("cash",),
    "TIPS": ("tips",),
    "Treasury": ("treasury",),
    "Equity": ("equity",),
    "Commodity": ("commodity",),
    "Currency": ("currency",),
    "Notional": ("notional", "total notional"),
    "NotionalChangeFromPriorMonth": ("notional change from prior month",),
    "AnnualizedVolatility": ("annualized volatility",),
}

_OUTPUT_COLUMNS: tuple[str, ...] = (
    "Segment",
    "Counterparty",
    "Cash",
    "TIPS",
    "Treasury",
    "Equity",
    "Commodity",
    "Currency",
    "Notional",
    "NotionalChangeFromPriorMonth",
    "AnnualizedVolatility",
    "SourceRow",
)

_OUTPUT_DTYPES: dict[str, str] = {
    "Segment": "string",
    "Counterparty": "string",
    "Cash": "float64",
    "TIPS": "float64",
    "Treasury": "float64",
    "Equity": "float64",
    "Commodity": "float64",
    "Currency": "float64",
    "Notional": "float64",
    "NotionalChangeFromPriorMonth": "float64",
    "AnnualizedVolatility": "float64",
    "SourceRow": "int64",
}


@dataclass(frozen=True)
class SegmentMetadata:
    """Segment boundary metadata in the source worksheet."""

    segment_type: str
    start_row: int
    label_text: str


def parse_cprs_ch(path: Path | str) -> pd.DataFrame:
    """Parse CPRS-CH content to one normalized table.

    Args:
        path: Path to a CPRS-CH `.xlsx` workbook.

    Returns:
        Normalized pandas DataFrame with stable schema.

    Raises:
        FileNotFoundError: If the input file does not exist.
        ValueError: If worksheet shape is malformed or segments are missing.
        ModuleNotFoundError: If pandas is not installed.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"CPRS-CH file not found: {file_path}")

    try:
        sheet_name, rows = _read_ch_sheet(file_path)
    except (KeyError, ET.ParseError, BadZipFile, ValueError) as exc:
        raise ValueError(f"Malformed CPRS-CH workbook structure: {file_path}") from exc

    header_row = _find_header_row(rows)
    if header_row is None:
        raise ValueError("Unable to locate CPRS-CH header row")

    column_map = _build_column_map(rows, header_row)
    if "Counterparty" not in column_map:
        column_map["Counterparty"] = 2
    if "Notional" not in column_map:
        raise ValueError("CPRS-CH workbook is missing required column: Notional")

    segments = _scan_segments(rows)
    if not segments:
        raise ValueError("No CPRS-CH segments detected")

    _validate_expected_segments(file_path=file_path, sheet_name=sheet_name, segments=segments)

    records: list[dict[str, object]] = []
    segment_ranges = _segment_ranges(segments, rows)

    for segment in segment_ranges:
        # Real exports often place the segment label (e.g. "Swaps", "Repo") in the
        # same physical row as the *first* data row (label in column A, data in
        # column B+) — include start_row in the scan rather than skipping it
        # unconditionally, and only drop it if the Counterparty-column cell on
        # that row turns out to be the marker label itself (no distinct data).
        for row_number in range(segment.start_row, segment.end_row + 1):
            row = rows.get(row_number, {})
            counterparty = _extract_text(row, column_map["Counterparty"])
            if not counterparty:
                continue

            if (
                row_number == segment.start_row
                and _identify_segment(counterparty) == segment.segment_type
            ):
                continue

            # Skip subtotal/footer/annotation noise rows (e.g. "Total Current Exposure",
            # "MOSERS Program", "Notional Breakdown", asterisked footnotes — some real
            # exports wrap the footnote text in literal straight/curly quote marks).
            footer_check_text = counterparty.lower().strip("\"'“”")
            if any(footer_check_text.startswith(prefix) for prefix in _FOOTER_ROW_PREFIXES):
                continue

            record = {
                "Segment": segment.segment_type,
                "Counterparty": counterparty,
                "Cash": _extract_numeric(row, column_map.get("Cash")),
                "TIPS": _extract_numeric(row, column_map.get("TIPS")),
                "Treasury": _extract_numeric(row, column_map.get("Treasury")),
                "Equity": _extract_numeric(row, column_map.get("Equity")),
                "Commodity": _extract_numeric(row, column_map.get("Commodity")),
                "Currency": _extract_numeric(row, column_map.get("Currency")),
                "Notional": _extract_numeric(row, column_map.get("Notional")),
                "NotionalChangeFromPriorMonth": _extract_numeric(
                    row, column_map.get("NotionalChangeFromPriorMonth")
                ),
                "AnnualizedVolatility": _extract_numeric(
                    row, column_map.get("AnnualizedVolatility")
                ),
                "SourceRow": row_number,
            }

            _validate_numeric_ranges(record, row_number)
            records.append(record)

    df = _to_dataframe(records)
    if df.empty:
        raise ValueError("CPRS-CH parser produced no rows")

    return df


@dataclass(frozen=True)
class _SegmentRange:
    segment_type: str
    start_row: int
    end_row: int


def _segment_ranges(
    segments: list[SegmentMetadata], rows: dict[int, dict[int, str | None]]
) -> list[_SegmentRange]:
    ordered = sorted(segments, key=lambda segment: segment.start_row)
    max_row = max(rows) if rows else 0
    ranges: list[_SegmentRange] = []
    for index, segment in enumerate(ordered):
        end_row = ordered[index + 1].start_row - 1 if index + 1 < len(ordered) else max_row
        ranges.append(
            _SegmentRange(
                segment_type=segment.segment_type, start_row=segment.start_row, end_row=end_row
            )
        )
    return ranges


def _validate_numeric_ranges(record: dict[str, object], row_number: int) -> None:
    numeric_columns = [
        "Cash",
        "TIPS",
        "Treasury",
        "Equity",
        "Commodity",
        "Currency",
        "Notional",
    ]

    for key in numeric_columns:
        raw_value = record[key]
        if not isinstance(raw_value, (int, float)):
            raise ValueError(
                f"Invalid non-numeric value for {key} at row {row_number}: {raw_value!r}"
            )
        value = float(raw_value)
        if not math.isfinite(value):
            raise ValueError(f"Invalid non-finite numeric value for {key} at row {row_number}")
        if abs(value) > 1_000_000_000_000_000:
            raise ValueError(f"Out-of-range numeric value for {key} at row {row_number}: {value}")


def _to_dataframe(records: list[dict[str, object]]) -> pd.DataFrame:
    try:
        import pandas as pd
    except ModuleNotFoundError as exc:  # pragma: no cover - environment-dependent
        raise ModuleNotFoundError(
            "parse_cprs_ch requires pandas to be installed in the runtime environment"
        ) from exc

    df = pd.DataFrame(records) if records else pd.DataFrame(columns=_OUTPUT_COLUMNS)

    for column in _OUTPUT_COLUMNS:
        if column not in df.columns:
            df[column] = (
                0.0 if column in _OUTPUT_DTYPES and _OUTPUT_DTYPES[column] == "float64" else ""
            )

    df = df.loc[:, list(_OUTPUT_COLUMNS)]
    return df.astype(_OUTPUT_DTYPES)


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return safe_display_name(value.replace("\n", " "))


def _matching_key(value: str | None) -> str:
    return canonicalize_name(_normalize_text(value)).casefold()


def _scan_segments(rows: dict[int, dict[int, str | None]]) -> list[SegmentMetadata]:
    segments: list[SegmentMetadata] = []
    for row_number in sorted(rows):
        row = rows[row_number]
        # Some MOSERS exports place segment labels in column B while legacy
        # drop-in templates place them in column A. At least one real export
        # additionally shifts the "Total by Counterparty/Clearing House" rollup
        # marker specifically into column C (the same column that holds
        # counterparty names in that file), with no text in A or B on that row.
        label = _normalize_text(row.get(1) or row.get(2) or row.get(3))
        if not label:
            continue

        segment_type = _identify_segment(label)
        if segment_type is None:
            continue

        segments.append(
            SegmentMetadata(segment_type=segment_type, start_row=row_number, label_text=label)
        )

    deduped: dict[tuple[str, int], SegmentMetadata] = {}
    for segment in segments:
        deduped[(segment.segment_type, segment.start_row)] = segment
    return sorted(deduped.values(), key=lambda segment: segment.start_row)


def _identify_segment(label: str) -> str | None:
    normalized = _matching_key(label)

    if normalized in _EXPECTED_SEGMENT_PATTERNS["futures_cdx"]:
        return "futures_cdx"

    if normalized.startswith(_TOTALS_SEGMENT_LABEL_PREFIX):
        return _TOTALS_SEGMENT_TYPE

    for segment_type, patterns in _EXPECTED_SEGMENT_PATTERNS.items():
        if segment_type == "futures_cdx":
            continue
        if any(pattern == normalized for pattern in patterns):
            return segment_type

    return None


def _validate_expected_segments(
    *, file_path: Path, sheet_name: str, segments: list[SegmentMetadata]
) -> None:
    expected = _expected_segments_for_variant(file_path=file_path, sheet_name=sheet_name)
    found_all = {segment.segment_type for segment in segments}
    # The "totals" rollup section is orthogonal to the swaps/repo/futures
    # classification these expectations are about — exclude it from these checks.
    found = found_all - {_TOTALS_SEGMENT_TYPE}

    # Trend files are occasionally labeled as "Swaps" despite futures-only rows.
    if expected == {"futures"} and "futures" not in found and found == {"swaps"}:
        original = next(s for s in segments if s.segment_type == "swaps")
        preserved = [s for s in segments if s.segment_type != "swaps"]
        segments.clear()
        segments.append(
            SegmentMetadata(
                segment_type="futures",
                start_row=original.start_row,
                label_text=original.label_text,
            )
        )
        segments.extend(preserved)
        found = {"futures"}

    missing = expected - found
    if missing:
        missing_labels = ", ".join(sorted(missing))
        raise ValueError(f"Missing expected CPRS-CH segments: {missing_labels}")


# Map each detected variant to the segment set required for validation.
# Order is significant in `_detect_variant`: the most-specific program-mix
# variant matches first, so e.g. `all_programs-mosers-input.xlsx` resolves
# to `all_programs` rather than being short-circuited by the mosers-input
# heuristic and dropping `futures_cdx` from the expected segments.
_VARIANT_SEGMENTS: dict[str, frozenset[str]] = {
    "ex_trend": frozenset({"swaps", "repo"}),
    # Trend fixtures are futures-only; some exports still label the section "Swaps".
    "trend": frozenset({"futures"}),
    "all_programs": frozenset({"swaps", "repo", "futures_cdx"}),
    "mosers_input": frozenset({"swaps", "repo"}),
}
_DEFAULT_EXPECTED_SEGMENTS: frozenset[str] = frozenset({"swaps", "repo"})


def _detect_variant(*, file_path: Path, sheet_name: str) -> str | None:
    title = normalize_variant_text(f"{file_path.name} {sheet_name}")
    if "ex trend" in title:
        return "ex_trend"
    if "all" in title:
        return "all_programs"
    # Generated pipeline artifacts often include both "trend" and
    # "mosers input" in the filename; prioritize the explicit
    # mosers-input marker so parser expectations match generated layout.
    if "mosers input" in title or "generated mosers" in title:
        return "mosers_input"
    if "trend" in title:
        return "trend"
    return None


def _expected_segments_for_variant(*, file_path: Path, sheet_name: str) -> set[str]:
    variant = _detect_variant(file_path=file_path, sheet_name=sheet_name)
    if variant is None:
        return set(_DEFAULT_EXPECTED_SEGMENTS)
    return set(_VARIANT_SEGMENTS[variant])


def _find_header_row(rows: dict[int, dict[int, str | None]]) -> int | None:
    numeric_headers = {"cash", "tips", "treasury", "equity", "commodity", "currency"}
    for row_number in sorted(rows):
        row = rows[row_number]
        normalized_values = [_matching_key(value) for value in row.values() if value]
        has_counterparty = any(
            "counterparty" in value or "clearing house" in value for value in normalized_values
        )
        has_notional = any("notional" in value for value in normalized_values)
        numeric_header_count = sum(
            1 for header_name in numeric_headers if header_name in normalized_values
        )
        if has_notional and (has_counterparty or numeric_header_count >= 3):
            return row_number
    return None


def _build_column_map(
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

        for canonical_name, aliases in _COLUMN_ALIASES.items():
            if canonical_name in column_map:
                continue
            if any(_header_matches_alias(canonical_name, normalized, alias) for alias in aliases):
                column_map[canonical_name] = column_index
                break

    return column_map


def _header_matches_alias(canonical_name: str, normalized_header: str, alias: str) -> bool:
    if canonical_name == "Notional":
        if normalized_header == alias:
            return True
        return normalized_header.endswith(alias) and "change" not in normalized_header
    return normalized_header == alias or alias in normalized_header


def _extract_text(row: dict[int, str | None], column_index: int) -> str:
    return _normalize_text(row.get(column_index))


def _extract_numeric(row: dict[int, str | None], column_index: int | None) -> float:
    if column_index is None:
        return 0.0
    return coerce_accounting_float(row.get(column_index), strip_percent=True)


def _read_ch_sheet(path: Path) -> tuple[str, dict[int, dict[int, str | None]]]:
    with ZipFile(path) as workbook_zip:
        try:
            sheet_name, sheet_path = resolve_sheet_target(
                workbook_zip,
                lambda name: any(alias in _matching_key(name) for alias in _CH_SHEET_ALIASES),
            )
        except ValueError as exc:
            raise ValueError("Unable to locate CPRS-CH worksheet") from exc

        shared_strings = load_shared_strings(workbook_zip)
        sheet_xml = ET.fromstring(workbook_zip.read(sheet_path))
        rows = read_sheet_rows(sheet_xml, shared_strings)

    return sheet_name, rows


_CLASS_BREAKDOWN_FIELDS: tuple[str, ...] = (
    "TIPS",
    "Treasury",
    "Equity",
    "Commodity",
    "Currency",
)
_BREAKDOWN_LABEL = "notional breakdown"
_ABSOLUTE_MARKER = "absolute"


def read_class_notional_breakdown(path: Path | str) -> dict[str, float] | None:
    """Read the published asset-class share row from a CPRS-CH worksheet.

    The MOSERS CPRS-CH tab publishes the class mix directly as a "Notional
    Breakdown" row, and the Trend workbook publishes a SECOND row, "Notional
    Breakdown (Absolute Values)". They differ materially: Trend holds short
    futures, so the signed row nets to a meaningless mix -- long and short
    positions cancel, and a class can even come out negative -- while the
    absolute row is what the report shows. The human process uses the absolute
    row when it exists, so prefer it here and fall back to the plain row.

    Note the absolute row is NOT recoverable by taking |value| of the parsed
    clearing-house rows: longs and shorts net within a clearing house before
    those rows are written, so a class's netted figure there can be materially
    smaller than its absolute figure. It must be read from the published row.

    Returns a mapping of asset class -> share, or None when no breakdown row is
    present (the caller then computes the mix from records as before).
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"CPRS-CH file not found: {file_path}")

    try:
        _sheet_name, rows = _read_ch_sheet(file_path)
    except (KeyError, ET.ParseError, BadZipFile, ValueError):
        return None

    header_row = _find_header_row(rows)
    if header_row is None:
        return None
    column_map = _build_column_map(rows, header_row)
    class_columns = {
        field: column_map[field] for field in _CLASS_BREAKDOWN_FIELDS if field in column_map
    }
    if not class_columns:
        return None

    plain_row: int | None = None
    absolute_row: int | None = None
    for row_number in sorted(rows):
        for cell_value in rows[row_number].values():
            text = _normalize_text(cell_value).casefold()
            if not text.startswith(_BREAKDOWN_LABEL):
                continue
            if _ABSOLUTE_MARKER in text:
                if absolute_row is None:
                    absolute_row = row_number
            elif plain_row is None:
                plain_row = row_number
            break

    chosen = absolute_row if absolute_row is not None else plain_row
    if chosen is None:
        return None

    breakdown: dict[str, float] = {}
    for field, column_index in class_columns.items():
        raw_value = rows[chosen].get(column_index)
        try:
            breakdown[field] = (
                coerce_accounting_float(raw_value, strip_percent=True)
                if raw_value not in (None, "")
                else 0.0
            )
        except (ValueError, TypeError):
            breakdown[field] = 0.0
    return breakdown
