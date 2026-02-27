from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.io.excel_range_compare import WorkbookRangeComparison, compare_workbook_ranges


def _write_workbook(path: Path, *, a1: object, b2: object, sheet_name: str = "Sheet1") -> None:
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_name
    worksheet["A1"] = a1
    worksheet["B2"] = b2
    workbook.save(path)
    workbook.close()


def test_compare_workbook_ranges_returns_no_differences_for_matching_ranges(tmp_path: Path) -> None:
    reference = tmp_path / "reference.xlsx"
    generated = tmp_path / "generated.xlsx"
    _write_workbook(reference, a1="alpha", b2=3.14)
    _write_workbook(generated, a1="alpha", b2=3.14)

    differences = compare_workbook_ranges(
        reference,
        generated,
        comparisons=(
            WorkbookRangeComparison(
                reference_sheet="Sheet1",
                generated_sheet="Sheet1",
                cell_range="A1:B2",
            ),
        ),
    )

    assert differences == []


def test_compare_workbook_ranges_reports_mismatched_cells(tmp_path: Path) -> None:
    reference = tmp_path / "reference.xlsx"
    generated = tmp_path / "generated.xlsx"
    _write_workbook(reference, a1="alpha", b2=3.14)
    _write_workbook(generated, a1="alpha", b2=2.71)

    differences = compare_workbook_ranges(
        reference,
        generated,
        comparisons=(
            WorkbookRangeComparison(
                reference_sheet="Sheet1",
                generated_sheet="Sheet1",
                cell_range="A1:B2",
            ),
        ),
    )

    assert len(differences) == 1
    assert "Sheet1!B2" in differences[0]
    assert "reference=3.14" in differences[0]
    assert "generated=2.71" in differences[0]


def test_compare_workbook_ranges_raises_for_missing_sheet(tmp_path: Path) -> None:
    reference = tmp_path / "reference.xlsx"
    generated = tmp_path / "generated.xlsx"
    _write_workbook(reference, a1="alpha", b2=3.14, sheet_name="Reference")
    _write_workbook(generated, a1="alpha", b2=3.14, sheet_name="Generated")

    with pytest.raises(ValueError, match="missing worksheet"):
        compare_workbook_ranges(
            reference,
            generated,
            comparisons=(
                WorkbookRangeComparison(
                    reference_sheet="Missing",
                    generated_sheet="Generated",
                    cell_range="A1:B2",
                ),
            ),
        )
