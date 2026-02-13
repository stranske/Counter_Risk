"""Parser for CPRS-CH inputs from NISA drop-in workbooks."""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from zipfile import BadZipFile, ZipFile

if TYPE_CHECKING:
    import pandas as pd

_XML_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

_EXPECTED_SEGMENT_PATTERNS: dict[str, tuple[str, ...]] = {
    "swaps": ("swaps",),
    "repo": ("repo",),
    "futures": ("futures",),
    "futures_cdx": ("futures cdx", "futures/cdx", "futures / cdx", "futures-cdx"),
}

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
        sheet_name, rows = _read_first_sheet(file_path)
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
        for row_number in range(segment.start_row + 1, segment.end_row + 1):
            row = rows.get(row_number, {})
            counterparty = _extract_text(row, column_map["Counterparty"])
            if not counterparty:
                continue

            # Stop before subtotal/footer noise.
            if counterparty.lower() in {"total", "subtotal"}:
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
        value = float(record[key])
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
    collapsed = re.sub(r"\s+", " ", value.replace("\n", " ")).strip()
    return collapsed


def _scan_segments(rows: dict[int, dict[int, str | None]]) -> list[SegmentMetadata]:
    segments: list[SegmentMetadata] = []
    for row_number in sorted(rows):
        label = _normalize_text(rows[row_number].get(1))
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
    normalized = _normalize_text(label).lower()

    if normalized in _EXPECTED_SEGMENT_PATTERNS["futures_cdx"]:
        return "futures_cdx"

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
    found = {segment.segment_type for segment in segments}

    # Trend files are occasionally labeled as "Swaps" despite futures-only rows.
    if expected == {"futures"} and "futures" not in found and found == {"swaps"}:
        original = segments[0]
        segments.clear()
        segments.append(
            SegmentMetadata(
                segment_type="futures",
                start_row=original.start_row,
                label_text=original.label_text,
            )
        )
        found = {"futures"}

    missing = expected - found
    if missing:
        missing_labels = ", ".join(sorted(missing))
        raise ValueError(f"Missing expected CPRS-CH segments: {missing_labels}")


def _expected_segments_for_variant(*, file_path: Path, sheet_name: str) -> set[str]:
    title = f"{file_path.name} {sheet_name}".lower()
    if "trend" in title and "ex trend" not in title:
        return {"futures"}
    if "ex trend" in title:
        return {"swaps", "repo"}
    if "all" in title:
        return {"swaps", "repo", "futures_cdx"}
    return {"swaps", "repo"}


def _find_header_row(rows: dict[int, dict[int, str | None]]) -> int | None:
    numeric_headers = {"cash", "tips", "treasury", "equity", "commodity", "currency"}
    for row_number in sorted(rows):
        row = rows[row_number]
        normalized_values = [_normalize_text(value).lower() for value in row.values() if value]
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
        ).lower()
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
        return normalized_header == alias
    return normalized_header == alias or alias in normalized_header


def _extract_text(row: dict[int, str | None], column_index: int) -> str:
    return _normalize_text(row.get(column_index))


def _extract_numeric(row: dict[int, str | None], column_index: int | None) -> float:
    if column_index is None:
        return 0.0

    raw_value = row.get(column_index)
    if raw_value is None:
        return 0.0

    text = _normalize_text(raw_value)
    if not text:
        return 0.0

    cleaned = text.replace(",", "").replace("$", "").replace("%", "")
    if cleaned in {"", "-", "--", "N/A", "n/a"}:
        return 0.0

    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"

    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"Unable to parse numeric value: {text}") from exc


def _read_first_sheet(path: Path) -> tuple[str, dict[int, dict[int, str | None]]]:
    with ZipFile(path) as workbook_zip:
        workbook_xml = ET.fromstring(workbook_zip.read("xl/workbook.xml"))
        rels_xml = ET.fromstring(workbook_zip.read("xl/_rels/workbook.xml.rels"))

        sheets = workbook_xml.find("main:sheets", _XML_NS)
        if sheets is None or len(list(sheets)) == 0:
            raise ValueError("Workbook contains no sheets")

        first_sheet = list(sheets)[0]
        sheet_name = first_sheet.attrib.get("name", "")
        relationship_id = first_sheet.attrib.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        if relationship_id is None:
            raise ValueError("Workbook sheet is missing relationship id")

        relationship_map = {
            relationship.attrib["Id"]: relationship.attrib["Target"]
            for relationship in rels_xml.findall("pkg:Relationship", _XML_NS)
        }

        target = relationship_map.get(relationship_id)
        if target is None:
            raise ValueError("Workbook sheet relationship target not found")

        sheet_path = f"xl/{target}" if not target.startswith("/") else target[1:]

        shared_strings = _load_shared_strings(workbook_zip)
        sheet_xml = ET.fromstring(workbook_zip.read(sheet_path))
        rows = _read_sheet_rows(sheet_xml, shared_strings)

    return sheet_name, rows


def _load_shared_strings(workbook_zip: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook_zip.namelist():
        return []

    shared_strings_xml = ET.fromstring(workbook_zip.read("xl/sharedStrings.xml"))
    output: list[str] = []

    for string_item in shared_strings_xml.findall("main:si", _XML_NS):
        text_nodes = string_item.findall(".//main:t", _XML_NS)
        output.append("".join(node.text or "" for node in text_nodes))

    return output


def _read_sheet_rows(
    sheet_xml: ET.Element, shared_strings: list[str]
) -> dict[int, dict[int, str | None]]:
    row_map: dict[int, dict[int, str | None]] = {}

    for row_node in sheet_xml.findall(".//main:sheetData/main:row", _XML_NS):
        row_number_text = row_node.attrib.get("r")
        if row_number_text is None:
            continue

        row_number = int(row_number_text)
        cells: dict[int, str | None] = {}

        for cell_node in row_node.findall("main:c", _XML_NS):
            reference = cell_node.attrib.get("r")
            if reference is None:
                continue

            column_index = _column_index_from_reference(reference)
            cells[column_index] = _cell_value(cell_node, shared_strings)

        row_map[row_number] = cells

    return row_map


def _cell_value(cell_node: ET.Element, shared_strings: list[str]) -> str | None:
    cell_type = cell_node.attrib.get("t")
    value_node = cell_node.find("main:v", _XML_NS)

    if cell_type == "inlineStr":
        inline_text_node = cell_node.find("main:is/main:t", _XML_NS)
        return inline_text_node.text if inline_text_node is not None else None

    if value_node is None:
        return None

    raw_value = value_node.text
    if raw_value is None:
        return None

    if cell_type == "s":
        index = int(raw_value)
        return shared_strings[index] if index < len(shared_strings) else None

    if cell_type == "b":
        return "TRUE" if raw_value == "1" else "FALSE"

    return raw_value


def _column_index_from_reference(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha()).upper()
    if not letters:
        raise ValueError(f"Invalid cell reference: {reference}")

    index = 0
    for character in letters:
        index = (index * 26) + (ord(character) - ord("A") + 1)

    return index
