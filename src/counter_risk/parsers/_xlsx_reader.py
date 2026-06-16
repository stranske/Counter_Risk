"""Shared raw-XLSX OOXML XML reader and numeric coercer."""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from collections.abc import Callable
from typing import Any
from zipfile import ZipFile

from counter_risk.normalize import canonicalize_name

_XML_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def load_shared_strings(workbook_zip: ZipFile) -> list[str]:
    """Load the shared strings list from an Excel workbook zip archive."""
    if "xl/sharedStrings.xml" not in workbook_zip.namelist():
        return []

    shared_strings_xml = ET.fromstring(workbook_zip.read("xl/sharedStrings.xml"))
    output: list[str] = []

    for string_item in shared_strings_xml.findall("main:si", _XML_NS):
        text_nodes = string_item.findall(".//main:t", _XML_NS)
        output.append("".join(node.text or "" for node in text_nodes))

    return output


def read_sheet_rows(
    sheet_xml: ET.Element, shared_strings: list[str]
) -> dict[int, dict[int, str | None]]:
    """Read cell values indexed by row and column from a sheet XML element."""
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

            column_index = column_index_from_reference(reference)
            cells[column_index] = cell_value(cell_node, shared_strings)

        row_map[row_number] = cells

    return row_map


def cell_value(cell_node: ET.Element, shared_strings: list[str]) -> str | None:
    """Extract and decode the cell value string from a cell XML node."""
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


def column_index_from_reference(reference: str) -> int:
    """Convert an Excel cell reference column (like 'A', 'B', 'AA') to a 1-based index."""
    letters = "".join(character for character in reference if character.isalpha()).upper()
    if not letters:
        raise ValueError(f"Invalid cell reference: {reference}")

    index = 0
    for character in letters:
        index = (index * 26) + (ord(character) - ord("A") + 1)

    return index


def resolve_sheet_target(
    workbook_zip: ZipFile,
    selector: Callable[[str], bool],
) -> tuple[str, str]:
    """Resolve the sheet name and XML target path using the selector predicate."""
    workbook_xml = ET.fromstring(workbook_zip.read("xl/workbook.xml"))
    rels_xml = ET.fromstring(workbook_zip.read("xl/_rels/workbook.xml.rels"))

    sheets = workbook_xml.find("main:sheets", _XML_NS)
    if sheets is None or len(list(sheets)) == 0:
        raise ValueError("Workbook contains no sheets")

    relationship_map = {
        relationship.attrib["Id"]: relationship.attrib["Target"]
        for relationship in rels_xml.findall("pkg:Relationship", _XML_NS)
    }

    for sheet in sheets.findall("main:sheet", _XML_NS):
        name = sheet.attrib.get("name", "")
        if selector(name):
            relationship_id = sheet.attrib.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
            if relationship_id is None:
                continue
            target = relationship_map.get(relationship_id)
            if target is None:
                continue
            sheet_path = f"xl/{target}" if not target.startswith("/") else target[1:]
            return name, sheet_path

    raise ValueError("Workbook sheet not found by selector")


def coerce_accounting_float(value: Any, *, strip_percent: bool = True) -> float:
    """Coerce a string or numeric cell value to a float.

    This function assumes a US-style number/locale where "," is used as a thousands
    separator and "." is used as the decimal separator (European format like "1.234,56"
    is not supported).

    If strip_percent is True, "%" symbols are stripped from the end, but the value
    is NOT rescaled by dividing by 100 (e.g., "5%" becomes 5.0, not 0.05).

    Non-finite floats (NaN, Inf, -Inf) are rejected by raising a ValueError.
    """
    if value is None:
        return 0.0

    if isinstance(value, (int, float)):
        val = float(value)
        if not math.isfinite(val):
            raise ValueError(f"Non-finite numeric value: {value}")
        return val

    # Normalization of string input
    text = canonicalize_name(str(value)).strip()
    if not text or text in {"-", "--", "N/A", "n/a"}:
        return 0.0

    # Handle parenthesized negative values, e.g. "(123.45)" -> "-123.45"
    if text.startswith("(") and text.endswith(")"):
        text = f"-{text[1:-1]}"

    # Strip currency symbols and separators
    cleaned = text.replace(",", "").replace("$", "")
    if strip_percent:
        cleaned = cleaned.replace("%", "")

    # Check for empty after cleanup (e.g., if it was just "$" or "%")
    if cleaned in {"", "-", "--"}:
        return 0.0

    try:
        val = float(cleaned)
    except ValueError as exc:
        raise ValueError(f"Unable to parse numeric cell value: {value!r}") from exc

    if not math.isfinite(val):
        raise ValueError(f"Non-finite numeric value parsed: {value!r}")

    return val
