"""Strict fixture parity tests for MOSERS workbook generation."""

from __future__ import annotations

from pathlib import Path

from counter_risk.writers.mosers_workbook import generate_mosers_workbook
from tests.utils.xlsx_compare import compare_workbooks


def test_generate_mosers_workbook_matches_reference_fixture_ranges(tmp_path: Path) -> None:
    destination = tmp_path / "MOSERS Generated - All Programs.xlsx"
    output_path = generate_mosers_workbook(
        raw_nisa_path=Path("tests/fixtures/NISA Monthly All Programs - Raw.xlsx"),
        output_path=destination,
    )

    compare_workbooks(
        reference_workbook=Path("tests/fixtures/mosers_reference.xlsx"),
        generated_workbook=output_path,
        sheet_names=["CPRS - CH", "CPRS - FCM"],
        ranges_by_sheet={
            "CPRS - CH": "A1:Z100",
            "CPRS - FCM": "A1:Z100",
        },
    )
