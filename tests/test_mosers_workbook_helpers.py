"""Focused edge-case coverage for MOSERS workbook generation helpers."""

from __future__ import annotations

from typing import Any

import pytest

from counter_risk.mosers import workbook_generation as generation
from counter_risk.parsers.nisa import NisaAllProgramsData, NisaTotalsRow


@pytest.fixture
def worksheet() -> Any:
    return pytest.importorskip("openpyxl").Workbook().active


def _total() -> NisaTotalsRow:
    return NisaTotalsRow(
        counterparty="Alpha",
        tips=1.0,
        treasury=2.0,
        equity=3.0,
        commodity=4.0,
        currency=5.0,
        notional=10.0,
        notional_change=6.0,
        annualized_volatility=0.2,
    )


def test_metric_values_cover_zero_total_and_unknown_metric() -> None:
    zero_total = _total().__class__(**{**_total().__dict__, "notional": 0.0})

    assert generation._build_allocation_percentages((zero_total,)) == [0.0]
    assert generation._build_totals_metric_values((_total(),), "annualized_volatility") == [0.2]
    with pytest.raises(ValueError, match="Unsupported totals source metric"):
        generation._build_totals_metric_values((_total(),), "unknown")


def test_section_helpers_write_clear_and_reject_invalid_markers(worksheet: Any) -> None:
    worksheet.title = "Totals"
    worksheet["A1"] = "Totals"
    worksheet["A4"] = "Stop"
    worksheet["C1"] = "before section"
    worksheet["C2"] = "stale first row"
    worksheet["C3"] = "stale unused row"
    worksheet["C4"] = "after section"
    worksheet["D2"] = "unmapped column"
    mappings = (generation.MosersPlugValueFieldMapping("counterparty", "C"),)

    assert generation._resolve_section_bounds(
        worksheet=worksheet, section_marker="Totals", stop_markers=("Stop",)
    ) == (2, 3)
    generation._write_totals_rows_by_marker(
        worksheet=worksheet,
        totals_rows=(_total(),),
        section_marker="Totals",
        stop_markers=("Stop",),
        field_mappings=mappings,
    )
    assert worksheet["C2"].value == "Alpha"
    assert worksheet["C3"].value is None
    generation._clear_totals_rows_by_marker(
        worksheet=worksheet,
        section_marker="Totals",
        stop_markers=("Stop",),
        field_mappings=mappings,
    )
    assert worksheet["C2"].value is None
    assert worksheet["C3"].value is None
    assert worksheet["C1"].value == "before section"
    assert worksheet["C4"].value == "after section"
    assert worksheet["D2"].value == "unmapped column"

    with pytest.raises(ValueError, match="Unable to resolve section marker"):
        generation._write_totals_rows_by_marker(
            worksheet=worksheet,
            totals_rows=(),
            section_marker="Missing",
            stop_markers=("Stop",),
            field_mappings=mappings,
        )
    with pytest.raises(ValueError, match="Unable to resolve section marker"):
        generation._clear_totals_rows_by_marker(
            worksheet=worksheet,
            section_marker="Missing",
            stop_markers=("Stop",),
            field_mappings=mappings,
        )


def test_section_bounds_cover_missing_marker_empty_range_and_no_stop(worksheet: Any) -> None:
    worksheet.title = "Bounds"
    assert (
        generation._resolve_section_bounds(
            worksheet=worksheet, section_marker="Missing", stop_markers=("Stop",)
        )
        is None
    )
    worksheet["A2"] = "Totals"
    worksheet["A3"] = "Stop"
    assert (
        generation._resolve_section_bounds(
            worksheet=worksheet, section_marker="Totals", stop_markers=("Stop",)
        )
        is None
    )
    worksheet["A3"] = None
    assert (
        generation._find_stop_row(worksheet=worksheet, start_row=3, stop_markers=("Stop",)) is None
    )
    assert generation._resolve_section_bounds(
        worksheet=worksheet, section_marker="Totals", stop_markers=("Stop",)
    ) == (3, 3)


def test_field_and_header_validation_errors(worksheet: Any) -> None:
    worksheet.title = "CPRS - CH"
    with pytest.raises(ValueError, match="Unsupported plug-values source field"):
        generation._get_totals_row_field_value(row=_total(), source_field="unknown")
    with pytest.raises(ValueError, match="expected CPRS-CH metric header"):
        generation._validate_metric_headers_present(worksheet)


def test_metric_column_resolution_handles_fallback_and_distant_duplicate(worksheet: Any) -> None:
    worksheet["D1"] = "Annualized Volatility"
    worksheet["J2"] = "Annualized Volatility"
    worksheet["E1"] = "%"

    assert generation._resolve_metric_target_columns(
        worksheet=worksheet,
        metrics=("annualized_volatility", "allocation_percentage", "missing"),
        fallback_columns={"annualized_volatility": "D", "allocation_percentage": "E"},
    ) == {"annualized_volatility": "D", "allocation_percentage": "E"}
    assert generation._resolve_metric_target_columns(
        worksheet=worksheet,
        metrics=("annualized_volatility",),
        section_start_row=1,
        fallback_columns={"annualized_volatility": "D"},
    ) == {"annualized_volatility": "D"}


def test_template_missing_sheet_closes_workbook_and_generator_reports_missing_sheets(
    monkeypatch: pytest.MonkeyPatch, worksheet: Any
) -> None:
    workbook = worksheet.parent
    workbook.remove(worksheet)
    workbook.create_sheet("Other")
    closed = False

    def close() -> None:
        nonlocal closed
        closed = True

    monkeypatch.setattr(workbook, "close", close)
    monkeypatch.setattr(generation, "load_mosers_template_workbook", lambda: workbook)
    with pytest.raises(ValueError, match="required MOSERS template sheet"):
        generation._resolve_cprs_ch_metric_row_bounds_from_template()
    assert closed

    parsed = NisaAllProgramsData(ch_rows=(), totals_rows=())
    structure = generation.MosersAllProgramsOutputStructure(
        required_sheets=("CPRS - CH", "CPRS - FCM"),
        cprs_ch_sheet="CPRS - CH",
        program_name_cell="B5",
        cprs_ch_metric_start_row=1,
        cprs_ch_metric_end_row=2,
    )
    with pytest.raises(ValueError, match="missing required sheet") as caught:
        generation._generate_mosers_workbook_from_parser(
            "ignored.xlsx", parser=lambda _: parsed, structure=structure
        )
    assert str(caught.value) == (
        "MOSERS template workbook missing required sheet(s): CPRS - CH, CPRS - FCM"
    )


def test_trend_variant_clears_the_non_applicable_fcm_totals_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parsed = NisaAllProgramsData(ch_rows=(), totals_rows=())
    template = generation.load_mosers_template_workbook()
    template_sheet = template["CPRS - FCM"]
    marker_row = generation._find_marker_row(
        worksheet=template_sheet, marker_text="Total by Counterparty/ FCM"
    )
    assert marker_row is not None
    template_sheet[f"C{marker_row + 1}"] = "stale value"
    monkeypatch.setattr(generation, "load_mosers_template_workbook", lambda: template)
    workbook = generation._generate_mosers_workbook_from_parser(
        "ignored.xlsx", parser=lambda _: parsed, variant="trend"
    )
    try:
        sheet = workbook["CPRS - FCM"]
        assert sheet[f"C{marker_row + 1}"].value is None
    finally:
        workbook.close()


@pytest.mark.parametrize(
    ("function_name", "variant"),
    [
        ("generate_mosers_workbook_ex_trend", "ex_trend"),
        ("generate_mosers_workbook_trend", "trend"),
    ],
)
def test_variant_wrappers_delegate_with_expected_variant(
    monkeypatch: pytest.MonkeyPatch, function_name: str, variant: str
) -> None:
    captured: dict[str, object] = {}

    def fake_generate(path: object, **kwargs: object) -> str:
        captured["path"] = path
        captured.update(kwargs)
        return "workbook"

    monkeypatch.setattr(generation, "_generate_mosers_workbook_from_parser", fake_generate)

    assert getattr(generation, function_name)("raw.xlsx") == "workbook"
    assert captured["path"] == "raw.xlsx"
    assert captured["variant"] == variant
