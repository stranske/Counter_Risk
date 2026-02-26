"""Tests for the Ex Trend MOSERS output structure contract."""

from __future__ import annotations

from pathlib import Path

from counter_risk.mosers.workbook_generation import (
    generate_mosers_workbook_ex_trend,
    get_mosers_ex_trend_output_structure,
    get_mosers_ex_trend_transformation_scope,
)
from counter_risk.parsers.nisa_ex_trend import parse_nisa_ex_trend


def test_ex_trend_output_structure_defines_expected_cprs_layout() -> None:
    structure = get_mosers_ex_trend_output_structure()

    assert structure.required_sheets == ("CPRS - CH", "CPRS - FCM")
    assert structure.cprs_ch_sheet == "CPRS - CH"
    assert structure.program_name_cell == "B5"
    assert (structure.start_row, structure.end_row) == (10, 20)


def test_ex_trend_transformation_scope_defines_core_mappings() -> None:
    scope = get_mosers_ex_trend_transformation_scope()

    assert scope.totals_source_name == "totals_rows"
    assert tuple(
        (transform.source_metric, transform.target_column) for transform in scope.cprs_ch_transforms
    ) == (
        ("annualized_volatility", "D"),
        ("allocation_percentage", "E"),
    )
    assert scope.overflow_policy == "truncate_to_layout"
    assert scope.underflow_policy == "clear_remaining_cells"


def test_ex_trend_fixture_generates_using_documented_layout_contract() -> None:
    fixture_path = Path("tests/fixtures/NISA Monthly Ex Trend - Raw.xlsx")
    structure = get_mosers_ex_trend_output_structure()
    scope = get_mosers_ex_trend_transformation_scope()
    parsed = parse_nisa_ex_trend(fixture_path)

    workbook = generate_mosers_workbook_ex_trend(fixture_path)
    try:
        assert set(structure.required_sheets).issubset(workbook.sheetnames)
        worksheet = workbook[structure.cprs_ch_sheet]

        assert worksheet[structure.program_name_cell].value == parsed.ch_rows[0].counterparty

        first_vol_column = next(
            transform.target_column
            for transform in scope.cprs_ch_transforms
            if transform.source_metric == "annualized_volatility"
        )
        first_alloc_column = next(
            transform.target_column
            for transform in scope.cprs_ch_transforms
            if transform.source_metric == "allocation_percentage"
        )
        first_vol_cell = f"{first_vol_column}{structure.start_row}"
        first_alloc_cell = f"{first_alloc_column}{structure.start_row}"

        assert worksheet[first_vol_cell].value == parsed.totals_rows[0].annualized_volatility

        total_notional = sum(row.notional for row in parsed.totals_rows)
        expected_allocation = (
            0.0 if total_notional == 0 else parsed.totals_rows[0].notional / total_notional
        )
        assert worksheet[first_alloc_cell].value == expected_allocation
    finally:
        workbook.close()
