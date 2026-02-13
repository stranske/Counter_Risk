"""Tests for the Runner.xlsm workbook scope artifact."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest

from counter_risk.runner_date_control import (
    DateControlRequirements,
    define_runner_xlsm_workbook_scope,
)
from scripts.build_runner_workbook import build_runner_workbook

SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RELATIONSHIP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

NAMESPACES = {
    "ss": SPREADSHEET_NS,
    "r": RELATIONSHIP_NS,
    "pr": PACKAGE_REL_NS,
}


def _read_xml(zip_file: ZipFile, member: str) -> ElementTree.Element:
    with zip_file.open(member) as handle:
        return ElementTree.fromstring(handle.read())  # noqa: S314


def test_runner_workbook_scope_doc_defines_creation_boundaries() -> None:
    scope_doc = Path("docs/runner_xlsm_workbook_scope.md").read_text(encoding="utf-8")

    assert "Create `Runner.xlsm`" in scope_doc
    assert "month selector" in scope_doc.lower()
    assert "In Scope" in scope_doc
    assert "Out Of Scope" in scope_doc


def test_default_runner_workbook_scope_uses_month_selector_layout() -> None:
    scope = define_runner_xlsm_workbook_scope()

    assert scope.workbook_path == "Runner.xlsm"
    assert scope.runner_sheet_name == "Runner"
    assert scope.control_data_sheet_name == "ControlData"
    assert scope.selector_label_cell == "A3"
    assert scope.selector_label_text == "As-Of Month"
    assert scope.selector_input_cell == "B3"
    assert scope.control_data_start_row == 2
    assert scope.month_source_start == (2020, 1)
    assert scope.month_source_end == (2035, 12)


def test_runner_workbook_scope_rejects_non_month_selector_decision() -> None:
    with pytest.raises(ValueError, match="month-selector"):
        define_runner_xlsm_workbook_scope(
            DateControlRequirements(
                month_end_reporting_process=False,
                cross_office_reliability_required=False,
                deterministic_ci_testability_required=False,
            )
        )


def test_workbook_builder_uses_scope_defined_sheet_names_and_selector_cells(tmp_path: Path) -> None:
    workbook_path = tmp_path / "runner-scoped.xlsm"
    build_runner_workbook(workbook_path)

    scope = define_runner_xlsm_workbook_scope()
    with ZipFile(workbook_path) as zip_file:
        workbook_root = _read_xml(zip_file, "xl/workbook.xml")
        workbook_rels_root = _read_xml(zip_file, "xl/_rels/workbook.xml.rels")

        sheets = workbook_root.findall("ss:sheets/ss:sheet", NAMESPACES)
        sheet_by_name = {sheet.attrib["name"]: sheet for sheet in sheets}

        assert scope.runner_sheet_name in sheet_by_name
        assert scope.control_data_sheet_name in sheet_by_name
        assert sheet_by_name[scope.control_data_sheet_name].attrib.get("state") == "hidden"

        rel_target_by_id = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in workbook_rels_root.findall("pr:Relationship", NAMESPACES)
        }
        runner_target = rel_target_by_id[
            sheet_by_name[scope.runner_sheet_name].attrib[f"{{{RELATIONSHIP_NS}}}id"]
        ]

        runner_sheet_root = _read_xml(zip_file, f"xl/{runner_target}")

        label_node = runner_sheet_root.find(
            (
                f"ss:sheetData/ss:row[@r='3']/ss:c[@r='{scope.selector_label_cell}']"
                "/ss:is/ss:t"
            ),
            NAMESPACES,
        )
        assert label_node is not None
        assert label_node.text == scope.selector_label_text

        validation = runner_sheet_root.find("ss:dataValidations/ss:dataValidation", NAMESPACES)
        assert validation is not None
        assert validation.attrib.get("sqref") == scope.selector_input_cell

        formula = validation.find("ss:formula1", NAMESPACES)
        assert formula is not None
        assert (
            formula.text
            == f"{scope.control_data_sheet_name}!$A$2:$A$193"
        )
