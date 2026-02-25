from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from counter_risk.io.workbook_compare import compare_workbooks


def _build_workbook(
    path: Path,
    *,
    cell_value: str,
    modified: datetime,
    last_modified_by: str,
    title: str | None = None,
) -> None:
    openpyxl = pytest.importorskip("openpyxl")

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet["A1"] = cell_value
    workbook.properties.modified = modified
    workbook.properties.lastModifiedBy = last_modified_by
    if title is not None:
        workbook.properties.title = title
    workbook.save(path)
    workbook.close()


def test_compare_workbooks_ignores_modified_timestamp_when_cells_match(tmp_path: Path) -> None:
    reference = tmp_path / "reference.xlsx"
    generated = tmp_path / "generated.xlsx"

    _build_workbook(
        reference,
        cell_value="same-value",
        modified=datetime(2026, 1, 31, 12, 0, 0),
        last_modified_by="qa-user",
    )
    _build_workbook(
        generated,
        cell_value="same-value",
        modified=datetime(2026, 2, 1, 9, 30, 0),
        last_modified_by="qa-user",
    )

    assert compare_workbooks(reference, generated) == []


def test_compare_workbooks_ignores_last_modified_by_when_cells_match(tmp_path: Path) -> None:
    reference = tmp_path / "reference.xlsx"
    generated = tmp_path / "generated.xlsx"

    _build_workbook(
        reference,
        cell_value="same-value",
        modified=datetime(2026, 1, 31, 12, 0, 0),
        last_modified_by="user-a",
    )
    _build_workbook(
        generated,
        cell_value="same-value",
        modified=datetime(2026, 1, 31, 12, 0, 0),
        last_modified_by="user-b",
    )

    assert compare_workbooks(reference, generated) == []


def test_compare_workbooks_reports_cell_differences_even_with_identical_metadata(
    tmp_path: Path,
) -> None:
    reference = tmp_path / "reference.xlsx"
    generated = tmp_path / "generated.xlsx"

    metadata_modified = datetime(2026, 1, 31, 12, 0, 0)
    metadata_user = "same-user"

    _build_workbook(
        reference,
        cell_value="value-a",
        modified=metadata_modified,
        last_modified_by=metadata_user,
    )
    _build_workbook(
        generated,
        cell_value="value-b",
        modified=metadata_modified,
        last_modified_by=metadata_user,
    )

    differences = compare_workbooks(reference, generated)

    assert differences
    assert "Member differs: xl/worksheets/sheet1.xml" in differences
    assert "Member differs: docProps/core.xml" not in differences


def test_compare_workbooks_metadata_only_differences_do_not_produce_diffs(tmp_path: Path) -> None:
    reference = tmp_path / "reference.xlsx"
    generated = tmp_path / "generated.xlsx"

    _build_workbook(
        reference,
        cell_value="stable-cell",
        modified=datetime(2026, 1, 15, 8, 0, 0),
        last_modified_by="first-user",
    )
    _build_workbook(
        generated,
        cell_value="stable-cell",
        modified=datetime(2026, 2, 20, 18, 45, 0),
        last_modified_by="second-user",
    )

    assert compare_workbooks(reference, generated) == []


def test_compare_workbooks_reports_nonvolatile_core_property_differences(tmp_path: Path) -> None:
    reference = tmp_path / "reference.xlsx"
    generated = tmp_path / "generated.xlsx"

    _build_workbook(
        reference,
        cell_value="stable-cell",
        modified=datetime(2026, 1, 15, 8, 0, 0),
        last_modified_by="first-user",
        title="Reference Title",
    )
    _build_workbook(
        generated,
        cell_value="stable-cell",
        modified=datetime(2026, 2, 20, 18, 45, 0),
        last_modified_by="second-user",
        title="Generated Title",
    )

    differences = compare_workbooks(reference, generated)

    assert any(diff.startswith("Core property differs: title") for diff in differences)
    assert not any("modified" in diff for diff in differences)
    assert not any("lastModifiedBy" in diff for diff in differences)
