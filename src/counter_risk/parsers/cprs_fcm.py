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

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import BadZipFile, ZipFile

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


def parse_fcm_totals(path: Path | str):  # -> pd.DataFrame
    """Parse totals-by-counterparty section from the CPRS-FCM worksheet."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"CPRS-FCM file not found: {file_path}")

    try:
        sheet_name, rows = _read_fcm_sheet(file_path)
    except (KeyError, ET.ParseError, BadZipFile, ValueError) as exc:
        raise ValueError(f"Malformed CPRS-FCM workbook structure: {file_path}") from exc

    if _variant_for_path(file_path=file_path, sheet_name=sheet_name) == "trend":
        return _to_dataframe(records=[], columns=_TOTAL_COLUMNS, dtypes=_TOTAL_DTYPES)

    boundaries = _locate_totals_section(rows)
    if boundaries is None:
        return _to_dataframe(records=[], columns=_TOTAL_COLUMNS, dtypes=_TOTAL_DTYPES)

    start_row, end_row = boundaries
    records: list[dict[str, object]] = []
    for row_number in range(start_row, end_row + 1):
        row = rows.get(row_number, {})
        counterparty = _normalize_text(row.get(3))
        if not counterparty:
            continue

        lowered = counterparty.lower()
        if lowered in {"total", "subtotal"}:
            continue
        if _FUTURES_SECTION_MARKER in lowered:
            continue

        notional_value = _extract_numeric(row.get(11))
        category_values = [_extract_numeric(row.get(index)) for index in (5, 6, 7, 8, 9)]
        if notional_value == 0.0 and all(value == 0.0 for value in category_values):
            continue

        records.append(
            {
                "counterparty": counterparty,
                "TIPS": _extract_numeric(row.get(5)),
                "Treasury": _extract_numeric(row.get(6)),
                "Equity": _extract_numeric(row.get(7)),
                "Commodity": _extract_numeric(row.get(8)),
                "Currency": _extract_numeric(row.get(9)),
                "Notional": notional_value,
                "NotionalChange": _extract_numeric(row.get(12)),
            }
        )

    return _to_dataframe(records=records, columns=_TOTAL_COLUMNS, dtypes=_TOTAL_DTYPES)


def parse_futures_detail(path: Path | str):  # -> pd.DataFrame
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
    records: list[dict[str, object]] = []
    for row_number in range(start_row, end_row + 1):
        row = rows.get(row_number, {})
        account = _normalize_text(row.get(3))
        description = _normalize_text(row.get(5))
        position_class = _normalize_text(row.get(7))
        fcm = _normalize_text(row.get(8))
        clearing_house = _normalize_text(row.get(9))

        if not account and not description and not _normalize_text(row.get(12)):
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
                "notional": _extract_numeric(row.get(12)),
            }
        )

    return _to_dataframe(records=records, columns=_FUTURES_COLUMNS, dtypes=_FUTURES_DTYPES)


def _locate_totals_section(rows: dict[int, dict[int, str | None]]) -> tuple[int, int] | None:
    marker_row: int | None = None
    for row_number in sorted(rows):
        row_text = _normalize_text(rows[row_number].get(3)).lower()
        if _TOTALS_SECTION_MARKER in row_text:
            marker_row = row_number
            break

    if marker_row is None:
        return None

    start_row = marker_row + 1
    end_row = max(rows)
    for row_number in range(start_row, max(rows) + 1):
        row_text = _normalize_text(rows.get(row_number, {}).get(3)).lower()
        if _FUTURES_SECTION_MARKER in row_text or _FUTURES_FOOTER_MARKER in row_text:
            end_row = row_number - 1
            break

    return start_row, max(start_row - 1, end_row)


def _locate_futures_detail_section(rows: dict[int, dict[int, str | None]]) -> tuple[int, int] | None:
    marker_row: int | None = None
    for row_number in sorted(rows):
        row_text = _normalize_text(rows[row_number].get(3)).lower()
        if _FUTURES_SECTION_MARKER in row_text:
            marker_row = row_number
            break

    if marker_row is None:
        return None

    header_row = marker_row + 1
    start_row = header_row + 1
    end_row = max(rows)
    for row_number in range(start_row, max(rows) + 1):
        row_text = _normalize_text(rows.get(row_number, {}).get(3)).lower()
        if _FUTURES_FOOTER_MARKER in row_text:
            end_row = row_number - 1
            break

    return start_row, max(start_row - 1, end_row)


def _variant_for_path(*, file_path: Path, sheet_name: str) -> str:
    title = f"{file_path.name} {sheet_name}".lower()
    if "ex trend" in title:
        return "ex_trend"
    if "trend" in title:
        return "trend"
    return "all_programs"


def _read_fcm_sheet(path: Path) -> tuple[str, dict[int, dict[int, str | None]]]:
    with ZipFile(path) as workbook_zip:
        workbook_xml = ET.fromstring(workbook_zip.read("xl/workbook.xml"))
        rels_xml = ET.fromstring(workbook_zip.read("xl/_rels/workbook.xml.rels"))
        sheets = workbook_xml.find("main:sheets", _XML_NS)
        if sheets is None:
            raise ValueError("Workbook contains no sheets")

        relationship_map = {
            relationship.attrib["Id"]: relationship.attrib["Target"]
            for relationship in rels_xml.findall("pkg:Relationship", _XML_NS)
        }

        selected_name = ""
        selected_target: str | None = None
        for sheet in sheets.findall("main:sheet", _XML_NS):
            name = sheet.attrib.get("name", "")
            normalized_name = _normalize_text(name).lower()
            if not any(alias in normalized_name for alias in _FCM_SHEET_ALIASES):
                continue

            relationship_id = sheet.attrib.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
            if relationship_id is None:
                continue
            target = relationship_map.get(relationship_id)
            if target is None:
                continue

            selected_name = name
            selected_target = target
            break

        if selected_target is None:
            raise ValueError("Unable to locate CPRS-FCM worksheet")

        sheet_path = f"xl/{selected_target}" if not selected_target.startswith("/") else selected_target[1:]
        shared_strings = _load_shared_strings(workbook_zip)
        sheet_xml = ET.fromstring(workbook_zip.read(sheet_path))
        rows = _read_sheet_rows(sheet_xml, shared_strings)

    return selected_name, rows


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


def _column_index_from_reference(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha()).upper()
    if not letters:
        raise ValueError(f"Invalid cell reference: {reference}")

    index = 0
    for character in letters:
        index = (index * 26) + (ord(character) - ord("A") + 1)
    return index


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


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value.replace("\n", " ")).strip()


def _extract_numeric(value: str | None) -> float:
    text = _normalize_text(value)
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


def _to_dataframe(
    *, records: list[dict[str, object]], columns: tuple[str, ...], dtypes: dict[str, str]
):
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
