"""Fixture smoke tests for macro-spec parity coverage."""

from __future__ import annotations

from typing import Any


def test_macro_spec_fixture_inputs_exist(macro_spec_cases: tuple[Any, ...]) -> None:
    for case in macro_spec_cases:
        assert (
            case.raw_input_path.is_file()
        ), f"Missing macro-spec fixture input for {case.variant}: {case.raw_input_path}"


def test_macro_spec_fixture_parsers_load_sample_inputs(
    parsed_macro_spec_data: dict[str, Any],
) -> None:
    for variant, parsed in parsed_macro_spec_data.items():
        assert parsed.ch_rows, f"{variant}: expected at least one CPRS-CH row from fixture input"
        assert parsed.totals_rows, f"{variant}: expected at least one totals row from fixture input"


def test_macro_spec_fixture_generators_create_cprs_ch_sheet(
    macro_spec_cases: tuple[Any, ...],
) -> None:
    for case in macro_spec_cases:
        workbook = case.generator(case.raw_input_path)
        try:
            assert (
                "CPRS - CH" in workbook.sheetnames
            ), f"{case.variant}: generated workbook missing required CPRS - CH sheet"
        finally:
            workbook.close()
