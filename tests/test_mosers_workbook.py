"""Tests for data-driven MOSERS workbook generation."""

from __future__ import annotations

from pathlib import Path
from shutil import copyfile
from typing import Any

import pytest

from counter_risk.mosers import workbook_generation as workbook_generation_module
from counter_risk.mosers.workbook_generation import (
    generate_mosers_workbook,
    generate_mosers_workbook_ex_trend,
    generate_mosers_workbook_trend,
    get_mosers_plug_values_mapping_requirements,
)
from counter_risk.parsers.nisa import (
    NisaAllProgramsData,
    NisaChRow,
    NisaTotalsRow,
    parse_nisa_all_programs,
)
from counter_risk.parsers.nisa_ex_trend import parse_nisa_ex_trend
from counter_risk.parsers.nisa_trend import parse_nisa_trend


def test_plug_values_mapping_requirements_define_supported_mosers_structures() -> None:
    requirements = get_mosers_plug_values_mapping_requirements()

    assert requirements.applicable_variants == ("all_programs", "ex_trend", "trend")
    assert tuple(
        (
            mapping.structure_name,
            mapping.target_sheet,
            mapping.source_rows_name,
            mapping.section_marker,
            mapping.stop_markers,
        )
        for mapping in requirements.structure_mappings
    ) == (
        (
            "cprs_ch_totals",
            "CPRS - CH",
            "totals_rows",
            "Total by Counterparty/Clearing House",
            ("Total Current Exposure", "MOSERS Program", "Notional Breakdown"),
        ),
        (
            "cprs_fcm_totals",
            "CPRS - FCM",
            "totals_rows",
            "Total by Counterparty/ FCM",
            ("FUTURES DETAIL",),
        ),
    )
    assert tuple(
        (field.source_field, field.target_column)
        for field in requirements.structure_mappings[0].field_mappings
    ) == (
        ("counterparty", "C"),
        ("tips", "E"),
        ("treasury", "F"),
        ("equity", "G"),
        ("commodity", "H"),
        ("currency", "I"),
        ("notional", "K"),
        ("notional_change", "L"),
    )


@pytest.mark.parametrize("fixture_path", [Path("tests/fixtures/raw_nisa_all_programs.xlsx")])
def test_generate_mosers_workbook_populates_program_name_from_parsed_nisa_data(
    fixture_path: Path,
) -> None:
    parsed = parse_nisa_all_programs(fixture_path)

    workbook = generate_mosers_workbook(fixture_path)
    try:
        worksheet = workbook["CPRS - CH"]
        assert worksheet["B5"].value == parsed.ch_rows[0].counterparty
        section_start, section_end = _find_metric_section_bounds(worksheet)
        slot_count = (section_end - section_start) + 1
        expected_vols = _pad_to_slot_count(
            [row.annualized_volatility for row in parsed.totals_rows], slot_count
        )
        expected_allocations = _pad_to_slot_count(_expected_allocations(parsed), slot_count)
        assert _read_column_values(worksheet, "D", section_start, section_end) == expected_vols
        assert (
            _read_column_values(worksheet, "E", section_start, section_end) == expected_allocations
        )

        first_total = parsed.totals_rows[0]
        ch_totals_start = _find_marker_row(worksheet, "Total by Counterparty/Clearing House") + 1
        assert _read_totals_row(worksheet, ch_totals_start) == (
            first_total.counterparty,
            first_total.tips,
            first_total.treasury,
            first_total.equity,
            first_total.commodity,
            first_total.currency,
            first_total.notional,
            first_total.notional_change,
        )

        fcm_sheet = workbook["CPRS - FCM"]
        fcm_totals_start = _find_marker_row(fcm_sheet, "Total by Counterparty/ FCM") + 1
        assert _read_totals_row(fcm_sheet, fcm_totals_start) == (
            first_total.counterparty,
            first_total.tips,
            first_total.treasury,
            first_total.equity,
            first_total.commodity,
            first_total.currency,
            first_total.notional,
            first_total.notional_change,
        )
    finally:
        workbook.close()


def test_generate_mosers_workbook_reflects_input_annualized_volatility_changes(
    tmp_path: Path,
) -> None:
    openpyxl = pytest.importorskip("openpyxl")

    base_input = Path("tests/fixtures/raw_nisa_all_programs.xlsx")
    variant_input = tmp_path / "raw_nisa_all_programs_variant.xlsx"
    copyfile(base_input, variant_input)

    source_workbook = openpyxl.load_workbook(variant_input)
    try:
        changed = _bump_first_annualized_volatility_column(source_workbook)
        assert changed, "Failed to edit annualized volatility values in fixture copy"
        source_workbook.save(variant_input)
    finally:
        source_workbook.close()

    base_workbook = generate_mosers_workbook(base_input)
    variant_workbook = generate_mosers_workbook(variant_input)
    try:
        base_sheet = base_workbook["CPRS - CH"]
        variant_sheet = variant_workbook["CPRS - CH"]
        base_start_row, _ = _find_metric_section_bounds(base_sheet)
        variant_start_row, _ = _find_metric_section_bounds(variant_sheet)
        assert (
            base_sheet[f"D{base_start_row}"].value != variant_sheet[f"D{variant_start_row}"].value
        )
    finally:
        base_workbook.close()
        variant_workbook.close()


def test_generate_mosers_workbook_truncates_values_to_documented_layout_slots() -> None:
    totals_rows = tuple(
        NisaTotalsRow(
            counterparty=f"Counterparty {index + 1}",
            tips=1.0,
            treasury=2.0,
            equity=3.0,
            commodity=4.0,
            currency=5.0,
            notional=float(index + 1),
            notional_change=0.0,
            annualized_volatility=100.0 + float(index),
        )
        for index in range(14)
    )
    parsed = NisaAllProgramsData(
        ch_rows=(
            NisaChRow(
                segment="swaps",
                counterparty="Counterparty 1",
                cash=0.0,
                tips=1.0,
                treasury=2.0,
                equity=3.0,
                commodity=4.0,
                currency=5.0,
                notional=1.0,
                notional_change=0.0,
                annualized_volatility=100.0,
            ),
        ),
        totals_rows=totals_rows,
    )

    workbook = workbook_generation_module._generate_mosers_workbook_from_parser(
        "ignored.xlsx", parser=lambda _path: parsed
    )
    try:
        worksheet = workbook["CPRS - CH"]
        section_start, section_end = _find_metric_section_bounds(worksheet)
        slot_count = (section_end - section_start) + 1
        assert _read_column_values(worksheet, "D", section_start, section_end) == [
            row.annualized_volatility for row in totals_rows[:slot_count]
        ]
    finally:
        workbook.close()


def test_generate_mosers_workbook_clears_unused_totals_slots_in_ch_and_fcm_sections() -> None:
    parsed = parse_nisa_all_programs(Path("tests/fixtures/raw_nisa_all_programs.xlsx"))
    workbook = generate_mosers_workbook(Path("tests/fixtures/raw_nisa_all_programs.xlsx"))
    try:
        for sheet_name, marker, stop_markers in (
            (
                "CPRS - CH",
                "Total by Counterparty/Clearing House",
                ("Total Current Exposure", "MOSERS Program", "Notional Breakdown"),
            ),
            ("CPRS - FCM", "Total by Counterparty/ FCM", ("FUTURES DETAIL",)),
        ):
            worksheet = workbook[sheet_name]
            marker_row = _find_marker_row(worksheet, marker)
            stop_row = _find_stop_row(worksheet, marker_row + 1, stop_markers)
            assert stop_row is not None

            first_unused_row = marker_row + 1 + len(parsed.totals_rows)
            if first_unused_row >= stop_row:
                continue

            assert _read_totals_row(worksheet, first_unused_row) == (
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            )
    finally:
        workbook.close()


def test_generate_mosers_workbook_applies_documented_plug_values_mappings() -> None:
    parsed = parse_nisa_all_programs(Path("tests/fixtures/raw_nisa_all_programs.xlsx"))
    workbook = generate_mosers_workbook(Path("tests/fixtures/raw_nisa_all_programs.xlsx"))
    requirements = get_mosers_plug_values_mapping_requirements()
    first_total = parsed.totals_rows[0]
    try:
        for structure in requirements.structure_mappings:
            worksheet = workbook[structure.target_sheet]
            marker_row = _find_marker_row(worksheet, structure.section_marker)
            first_data_row = marker_row + 1

            assert tuple(
                worksheet[f"{field_mapping.target_column}{first_data_row}"].value
                for field_mapping in structure.field_mappings
            ) == tuple(
                getattr(first_total, field_mapping.source_field)
                for field_mapping in structure.field_mappings
            )
    finally:
        workbook.close()


@pytest.mark.parametrize(
    ("fixture_path", "parser", "generator"),
    [
        (
            Path("tests/fixtures/raw_nisa_all_programs.xlsx"),
            parse_nisa_all_programs,
            generate_mosers_workbook,
        ),
        (
            Path("tests/fixtures/NISA Monthly Ex Trend - Raw.xlsx"),
            parse_nisa_ex_trend,
            generate_mosers_workbook_ex_trend,
        ),
        (
            Path("tests/fixtures/NISA Monthly Trend - Raw.xlsx"),
            parse_nisa_trend,
            generate_mosers_workbook_trend,
        ),
    ],
)
def test_generate_mosers_workbook_variants_apply_plug_values_consistently(
    fixture_path: Path,
    parser: Any,
    generator: Any,
) -> None:
    parsed = parser(fixture_path)
    workbook = generator(fixture_path)
    requirements = get_mosers_plug_values_mapping_requirements()
    first_total = parsed.totals_rows[0]
    try:
        for structure in requirements.structure_mappings:
            worksheet = workbook[structure.target_sheet]
            marker_row = _find_marker_row(worksheet, structure.section_marker)
            first_data_row = marker_row + 1
            assert _read_totals_row(worksheet, first_data_row) == (
                first_total.counterparty,
                first_total.tips,
                first_total.treasury,
                first_total.equity,
                first_total.commodity,
                first_total.currency,
                first_total.notional,
                first_total.notional_change,
            )
    finally:
        workbook.close()


def test_generate_mosers_workbook_ex_trend_populates_values_from_ex_trend_fixture() -> None:
    fixture_path = Path("tests/fixtures/NISA Monthly Ex Trend - Raw.xlsx")
    parsed = parse_nisa_ex_trend(fixture_path)

    workbook = generate_mosers_workbook_ex_trend(fixture_path)
    try:
        worksheet = workbook["CPRS - CH"]
        assert worksheet["B5"].value == parsed.ch_rows[0].counterparty
        section_start, section_end = _find_metric_section_bounds(worksheet)
        slot_count = (section_end - section_start) + 1
        expected_vols = _pad_to_slot_count(
            [row.annualized_volatility for row in parsed.totals_rows], slot_count
        )
        expected_allocations = _pad_to_slot_count(_expected_allocations(parsed), slot_count)
        assert _read_column_values(worksheet, "D", section_start, section_end) == expected_vols
        assert (
            _read_column_values(worksheet, "E", section_start, section_end) == expected_allocations
        )
    finally:
        workbook.close()


def test_generate_mosers_workbook_trend_populates_values_from_trend_fixture() -> None:
    fixture_path = Path("tests/fixtures/NISA Monthly Trend - Raw.xlsx")
    parsed = parse_nisa_trend(fixture_path)

    workbook = generate_mosers_workbook_trend(fixture_path)
    try:
        worksheet = workbook["CPRS - CH"]
        assert worksheet["B5"].value == parsed.ch_rows[0].counterparty
        section_start, section_end = _find_metric_section_bounds(worksheet)
        slot_count = (section_end - section_start) + 1
        expected_vols = _pad_to_slot_count(
            [row.annualized_volatility for row in parsed.totals_rows], slot_count
        )
        expected_allocations = _pad_to_slot_count(_expected_allocations(parsed), slot_count)
        assert _read_column_values(worksheet, "D", section_start, section_end) == expected_vols
        assert (
            _read_column_values(worksheet, "E", section_start, section_end) == expected_allocations
        )
    finally:
        workbook.close()


def _bump_first_annualized_volatility_column(workbook: Any) -> bool:
    for sheet_name in workbook.sheetnames:
        worksheet = workbook[sheet_name]
        max_row = int(worksheet.max_row)
        max_col = int(worksheet.max_column)

        target_col = 0
        header_row = 0
        for row_number in range(1, min(max_row, 200) + 1):
            for col_number in range(1, max_col + 1):
                value = worksheet.cell(row=row_number, column=col_number).value
                text = " ".join(str(value or "").split()).strip().casefold()
                if "annualized volatility" in text:
                    target_col = col_number
                    header_row = row_number
                    break
            if target_col:
                break

        if not target_col:
            continue

        edited = False
        for row_number in range(header_row + 1, max_row + 1):
            cell = worksheet.cell(row=row_number, column=target_col)
            value = cell.value
            if isinstance(value, (int, float)):
                cell.value = float(value) + 0.25
                edited = True

        if edited:
            return True

    return False


def _read_column_values(
    worksheet: Any, column: str, start_row: int, end_row: int
) -> list[float | None]:
    return [
        worksheet[f"{column}{row_number}"].value for row_number in range(start_row, end_row + 1)
    ]


def _expected_allocations(parsed_data: Any) -> list[float]:
    total_notional = sum(row.notional for row in parsed_data.totals_rows)
    if total_notional == 0:
        return [0.0 for _ in parsed_data.totals_rows]
    return [row.notional / total_notional for row in parsed_data.totals_rows]


def _pad_to_slot_count(values: list[float], slots: int) -> list[float | None]:
    if len(values) >= slots:
        trimmed: list[float | None] = [*values[:slots]]
        return trimmed
    return [*values, *([None] * (slots - len(values)))]


def _find_marker_row(worksheet: Any, marker: str) -> int:
    marker_text = " ".join(marker.split()).strip().casefold()
    for row_number in range(1, int(worksheet.max_row) + 1):
        value = worksheet[f"C{row_number}"].value
        normalized = " ".join(str(value or "").split()).strip().casefold()
        if marker_text in normalized:
            return row_number
    raise AssertionError(f"Unable to locate marker row containing {marker!r}")


def _read_totals_row(worksheet: Any, row_number: int) -> tuple[Any, ...]:
    return (
        worksheet[f"C{row_number}"].value,
        worksheet[f"E{row_number}"].value,
        worksheet[f"F{row_number}"].value,
        worksheet[f"G{row_number}"].value,
        worksheet[f"H{row_number}"].value,
        worksheet[f"I{row_number}"].value,
        worksheet[f"K{row_number}"].value,
        worksheet[f"L{row_number}"].value,
    )


def _find_stop_row(worksheet: Any, start_row: int, stop_markers: tuple[str, ...]) -> int | None:
    normalized_markers = tuple(
        " ".join(marker.split()).strip().casefold() for marker in stop_markers
    )
    for row_number in range(start_row, int(worksheet.max_row) + 1):
        value = worksheet[f"C{row_number}"].value
        normalized = " ".join(str(value or "").split()).strip().casefold()
        if any(marker in normalized for marker in normalized_markers):
            return row_number
    return None


def _find_metric_section_bounds(worksheet: Any) -> tuple[int, int]:
    """Return the fixed metric section bounds used by the MOSERS workbook generator."""
    from counter_risk.mosers.workbook_generation import _CH_METRIC_END_ROW, _CH_METRIC_START_ROW

    return (_CH_METRIC_START_ROW, _CH_METRIC_END_ROW)
