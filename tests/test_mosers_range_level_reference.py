from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.io.excel_range_compare import WorkbookRangeComparison, compare_workbook_ranges
from counter_risk.mosers.workbook_generation import generate_mosers_workbook
from tests.mosers_reference_outputs import get_mosers_reference_output_paths


def test_mosers_reference_outputs_exist_for_each_variant() -> None:
    openpyxl = pytest.importorskip("openpyxl")
    references = get_mosers_reference_output_paths()

    assert set(references) == {"all_programs", "ex_trend", "trend"}
    for path in references.values():
        assert path.exists(), f"Missing approved MOSERS reference workbook: {path}"
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            assert "CPRS - CH" in workbook.sheetnames
        finally:
            workbook.close()


def test_all_programs_generated_output_matches_reference_for_scoped_label_ranges(
    tmp_path: Path,
) -> None:
    generated_path = tmp_path / "all-programs-generated.xlsx"
    generated_workbook = generate_mosers_workbook(
        Path("tests/fixtures/NISA Monthly All Programs - Raw.xlsx")
    )
    try:
        generated_workbook.save(generated_path)
    finally:
        generated_workbook.close()

    reference_path = get_mosers_reference_output_paths()["all_programs"]
    differences = compare_workbook_ranges(
        reference_path,
        generated_path,
        comparisons=(
            WorkbookRangeComparison(
                reference_sheet="CPRS - CH",
                generated_sheet="CPRS - CH",
                cell_range="N5:N5",
            ),
            WorkbookRangeComparison(
                reference_sheet="CPRS - CH",
                generated_sheet="CPRS - CH",
                cell_range="C30:C30",
            ),
            WorkbookRangeComparison(
                reference_sheet="CPRS - CH",
                generated_sheet="CPRS - CH",
                cell_range="C48:C52",
            ),
        ),
    )

    assert differences == []
