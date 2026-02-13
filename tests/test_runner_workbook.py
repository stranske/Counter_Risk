"""Tests for the Excel Runner workbook artifact."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RELATIONSHIP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

NAMESPACES = {
    "ss": SPREADSHEET_NS,
    "r": RELATIONSHIP_NS,
    "pr": PACKAGE_REL_NS,
}


def _is_month_end(iso_date: str) -> bool:
    parsed = date.fromisoformat(iso_date)
    next_day = parsed.fromordinal(parsed.toordinal() + 1)
    return next_day.month != parsed.month


def _next_month_end(current: date) -> date:
    next_month_start = (
        date(current.year + 1, 1, 1)
        if current.month == 12
        else date(current.year, current.month + 1, 1)
    )
    month_after_next_start = (
        date(next_month_start.year + 1, 1, 1)
        if next_month_start.month == 12
        else date(next_month_start.year, next_month_start.month + 1, 1)
    )
    return month_after_next_start.fromordinal(month_after_next_start.toordinal() - 1)


def _read_xml(zip_file: ZipFile, member: str) -> ElementTree.Element:
    with zip_file.open(member) as handle:
        return ElementTree.fromstring(handle.read())  # noqa: S314


def test_runner_workbook_exists() -> None:
    assert Path("Runner.xlsm").is_file(), "Runner.xlsm must be committed to the repository root."


def test_runner_workbook_contains_month_selector_dropdown() -> None:
    workbook_path = Path("Runner.xlsm")
    with ZipFile(workbook_path) as zip_file:
        workbook_root = _read_xml(zip_file, "xl/workbook.xml")
        workbook_rels_root = _read_xml(zip_file, "xl/_rels/workbook.xml.rels")

        sheets = workbook_root.findall("ss:sheets/ss:sheet", NAMESPACES)
        sheet_by_name = {sheet.attrib["name"]: sheet for sheet in sheets}

        assert "Runner" in sheet_by_name
        assert "ControlData" in sheet_by_name
        assert sheet_by_name["ControlData"].attrib.get("state") == "hidden"

        rel_target_by_id = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in workbook_rels_root.findall("pr:Relationship", NAMESPACES)
        }

        runner_sheet_target = rel_target_by_id[
            sheet_by_name["Runner"].attrib[f"{{{RELATIONSHIP_NS}}}id"]
        ]
        control_sheet_target = rel_target_by_id[
            sheet_by_name["ControlData"].attrib[f"{{{RELATIONSHIP_NS}}}id"]
        ]

        runner_sheet_root = _read_xml(zip_file, f"xl/{runner_sheet_target}")
        control_sheet_root = _read_xml(zip_file, f"xl/{control_sheet_target}")

        selector_label = runner_sheet_root.find(
            "ss:sheetData/ss:row[@r='3']/ss:c[@r='A3']/ss:is/ss:t",
            NAMESPACES,
        )
        assert selector_label is not None
        assert selector_label.text == "As-Of Month"

        validations = runner_sheet_root.findall("ss:dataValidations/ss:dataValidation", NAMESPACES)
        assert validations, "Runner sheet must include data validation on the month selector cell."

        month_validation = next(
            (item for item in validations if item.attrib.get("sqref") == "B3"), None
        )
        assert month_validation is not None
        assert month_validation.attrib.get("type") == "list"

        formula = month_validation.find("ss:formula1", NAMESPACES)
        assert formula is not None
        assert formula.text == "ControlData!$A$2:$A$193"

        month_cells = control_sheet_root.findall("ss:sheetData/ss:row/ss:c/ss:is/ss:t", NAMESPACES)
        month_values = [cell.text for cell in month_cells if cell.text is not None]

        assert month_values[0] == "MonthEnd"
        assert month_values[1] == "2020-01-31"
        assert month_values[-1] == "2035-12-31"
        assert all(_is_month_end(item) for item in month_values[1:])

        parsed_dates = [date.fromisoformat(item) for item in month_values[1:]]
        for current, next_value in zip(parsed_dates, parsed_dates[1:], strict=False):
            assert next_value == _next_month_end(current)


def test_runner_workbook_contains_run_controls() -> None:
    workbook_path = Path("Runner.xlsm")
    with ZipFile(workbook_path) as zip_file:
        workbook_root = _read_xml(zip_file, "xl/workbook.xml")
        workbook_rels_root = _read_xml(zip_file, "xl/_rels/workbook.xml.rels")

        sheets = workbook_root.findall("ss:sheets/ss:sheet", NAMESPACES)
        sheet_by_name = {sheet.attrib["name"]: sheet for sheet in sheets}
        rel_target_by_id = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in workbook_rels_root.findall("pr:Relationship", NAMESPACES)
        }

        runner_sheet_target = rel_target_by_id[
            sheet_by_name["Runner"].attrib[f"{{{RELATIONSHIP_NS}}}id"]
        ]
        runner_sheet_root = _read_xml(zip_file, f"xl/{runner_sheet_target}")

        action_cells = {
            "A5": "Run All",
            "B5": "Run Ex Trend",
            "C5": "Run Trend",
            "D5": "Open Output Folder",
        }
        for cell_ref, expected_text in action_cells.items():
            node = runner_sheet_root.find(
                f"ss:sheetData/ss:row[@r='5']/ss:c[@r='{cell_ref}']/ss:is/ss:t",
                NAMESPACES,
            )
            assert node is not None
            assert node.text == expected_text
