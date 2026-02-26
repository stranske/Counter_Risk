"""Data-driven MOSERS workbook generation from raw NISA inputs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeAlias

from counter_risk.mosers.template import load_mosers_template_workbook
from counter_risk.parsers.nisa import (
    NisaAllProgramsData,
    NisaTotalsRow,
    parse_nisa_all_programs,
)
from counter_risk.parsers.nisa_ex_trend import parse_nisa_ex_trend
from counter_risk.parsers.nisa_trend import parse_nisa_trend

Workbook: TypeAlias = Any
Worksheet: TypeAlias = Any

_REQUIRED_SHEETS = ("CPRS - CH", "CPRS - FCM")
_TARGET_SHEET = "CPRS - CH"
_FCM_SHEET = "CPRS - FCM"
_PROGRAM_NAME_CELL = "B5"
_START_ROW = 10
_END_ROW = 20
_SECTION_LABEL_COLUMN = "C"
_CH_TOTALS_MARKER = "Total by Counterparty/Clearing House"
_CH_TOTALS_STOP_MARKERS = ("Total Current Exposure", "MOSERS Program", "Notional Breakdown")
_FCM_TOTALS_MARKER = "Total by Counterparty/ FCM"
_FCM_TOTALS_STOP_MARKERS = ("FUTURES DETAIL",)
_PLUG_VALUES_SOURCE_NAME = "totals_rows"
_PLUG_VALUES_APPLICABLE_VARIANTS = ("all_programs", "ex_trend", "trend")


@dataclass(frozen=True)
class MosersAllProgramsOutputStructure:
    """Expected MOSERS workbook layout for All Programs generation."""

    required_sheets: tuple[str, ...]
    cprs_ch_sheet: str
    program_name_cell: str
    start_row: int
    end_row: int


@dataclass(frozen=True)
class MosersColumnTransform:
    """Single source-to-target mapping used by MOSERS workbook generation."""

    source_metric: str
    target_column: str


@dataclass(frozen=True)
class MosersAllProgramsTransformationScope:
    """Core transformation contract for All Programs MOSERS workbook generation."""

    totals_source_name: str
    cprs_ch_transforms: tuple[MosersColumnTransform, ...]
    overflow_policy: str
    underflow_policy: str


@dataclass(frozen=True)
class MosersPlugValueFieldMapping:
    """Single source-field to target-column mapping for plug-values writes."""

    source_field: str
    target_column: str


@dataclass(frozen=True)
class MosersPlugValueStructureMapping:
    """Plug-values mapping contract for one target MOSERS structure section."""

    structure_name: str
    target_sheet: str
    source_rows_name: str
    section_marker: str
    stop_markers: tuple[str, ...]
    field_mappings: tuple[MosersPlugValueFieldMapping, ...]


@dataclass(frozen=True)
class MosersPlugValuesMappingRequirements:
    """All applicable plug-values mappings for MOSERS workbook generation."""

    applicable_variants: tuple[str, ...]
    structure_mappings: tuple[MosersPlugValueStructureMapping, ...]


def get_mosers_all_programs_output_structure() -> MosersAllProgramsOutputStructure:
    """Return the output-structure contract used for All Programs workbook generation."""

    return MosersAllProgramsOutputStructure(
        required_sheets=_REQUIRED_SHEETS,
        cprs_ch_sheet=_TARGET_SHEET,
        program_name_cell=_PROGRAM_NAME_CELL,
        start_row=_START_ROW,
        end_row=_END_ROW,
    )


def get_mosers_all_programs_transformation_scope() -> MosersAllProgramsTransformationScope:
    """Return the scoped source-to-target mappings for core All Programs transforms."""

    return MosersAllProgramsTransformationScope(
        totals_source_name="totals_rows",
        cprs_ch_transforms=(
            MosersColumnTransform(source_metric="annualized_volatility", target_column="D"),
            MosersColumnTransform(source_metric="allocation_percentage", target_column="E"),
        ),
        overflow_policy="truncate_to_layout",
        underflow_policy="clear_remaining_cells",
    )


def get_mosers_ex_trend_output_structure() -> MosersAllProgramsOutputStructure:
    """Return the output-structure contract used for Ex Trend workbook generation."""

    return MosersAllProgramsOutputStructure(
        required_sheets=_REQUIRED_SHEETS,
        cprs_ch_sheet=_TARGET_SHEET,
        program_name_cell=_PROGRAM_NAME_CELL,
        start_row=_START_ROW,
        end_row=_END_ROW,
    )


def get_mosers_ex_trend_transformation_scope() -> MosersAllProgramsTransformationScope:
    """Return the scoped source-to-target mappings for Ex Trend transforms."""

    return MosersAllProgramsTransformationScope(
        totals_source_name="totals_rows",
        cprs_ch_transforms=(
            MosersColumnTransform(source_metric="annualized_volatility", target_column="D"),
            MosersColumnTransform(source_metric="allocation_percentage", target_column="E"),
        ),
        overflow_policy="truncate_to_layout",
        underflow_policy="clear_remaining_cells",
    )


def get_mosers_trend_output_structure() -> MosersAllProgramsOutputStructure:
    """Return the output-structure contract used for Trend workbook generation."""

    return MosersAllProgramsOutputStructure(
        required_sheets=_REQUIRED_SHEETS,
        cprs_ch_sheet=_TARGET_SHEET,
        program_name_cell=_PROGRAM_NAME_CELL,
        start_row=_START_ROW,
        end_row=_END_ROW,
    )


def get_mosers_trend_transformation_scope() -> MosersAllProgramsTransformationScope:
    """Return the scoped source-to-target mappings for Trend transforms."""

    return MosersAllProgramsTransformationScope(
        totals_source_name="totals_rows",
        cprs_ch_transforms=(
            MosersColumnTransform(source_metric="annualized_volatility", target_column="D"),
            MosersColumnTransform(source_metric="allocation_percentage", target_column="E"),
        ),
        overflow_policy="truncate_to_layout",
        underflow_policy="clear_remaining_cells",
    )


def get_mosers_plug_values_mapping_requirements() -> MosersPlugValuesMappingRequirements:
    """Return documented plug-values mappings across all applicable MOSERS structures."""

    totals_field_mappings = (
        MosersPlugValueFieldMapping(source_field="counterparty", target_column="C"),
        MosersPlugValueFieldMapping(source_field="tips", target_column="E"),
        MosersPlugValueFieldMapping(source_field="treasury", target_column="F"),
        MosersPlugValueFieldMapping(source_field="equity", target_column="G"),
        MosersPlugValueFieldMapping(source_field="commodity", target_column="H"),
        MosersPlugValueFieldMapping(source_field="currency", target_column="I"),
        MosersPlugValueFieldMapping(source_field="notional", target_column="K"),
        MosersPlugValueFieldMapping(source_field="notional_change", target_column="L"),
    )
    return MosersPlugValuesMappingRequirements(
        applicable_variants=_PLUG_VALUES_APPLICABLE_VARIANTS,
        structure_mappings=(
            MosersPlugValueStructureMapping(
                structure_name="cprs_ch_totals",
                target_sheet=_TARGET_SHEET,
                source_rows_name=_PLUG_VALUES_SOURCE_NAME,
                section_marker=_CH_TOTALS_MARKER,
                stop_markers=_CH_TOTALS_STOP_MARKERS,
                field_mappings=totals_field_mappings,
            ),
            MosersPlugValueStructureMapping(
                structure_name="cprs_fcm_totals",
                target_sheet=_FCM_SHEET,
                source_rows_name=_PLUG_VALUES_SOURCE_NAME,
                section_marker=_FCM_TOTALS_MARKER,
                stop_markers=_FCM_TOTALS_STOP_MARKERS,
                field_mappings=totals_field_mappings,
            ),
        ),
    )


def generate_mosers_workbook(raw_nisa_path: str | Path) -> Workbook:
    """Generate a populated MOSERS workbook from raw NISA input.

    The internal MOSERS template workbook is loaded from package resources,
    parsed NISA values are written to fixed target cells/ranges, and the
    populated openpyxl workbook is returned without writing it to disk.
    """

    return _generate_mosers_workbook_from_parser(
        raw_nisa_path,
        parser=parse_nisa_all_programs,
        structure=get_mosers_all_programs_output_structure(),
        transformation_scope=get_mosers_all_programs_transformation_scope(),
    )


def generate_mosers_workbook_ex_trend(raw_nisa_path: str | Path) -> Workbook:
    """Generate a populated MOSERS workbook from raw NISA Ex Trend input."""

    return _generate_mosers_workbook_from_parser(
        raw_nisa_path,
        parser=parse_nisa_ex_trend,
        structure=get_mosers_ex_trend_output_structure(),
        transformation_scope=get_mosers_ex_trend_transformation_scope(),
    )


def generate_mosers_workbook_trend(raw_nisa_path: str | Path) -> Workbook:
    """Generate a populated MOSERS workbook from raw NISA Trend input."""

    return _generate_mosers_workbook_from_parser(
        raw_nisa_path,
        parser=parse_nisa_trend,
        structure=get_mosers_trend_output_structure(),
        transformation_scope=get_mosers_trend_transformation_scope(),
    )


def _generate_mosers_workbook_from_parser(
    raw_nisa_path: str | Path,
    *,
    parser: Callable[[str | Path], NisaAllProgramsData],
    structure: MosersAllProgramsOutputStructure | None = None,
    transformation_scope: MosersAllProgramsTransformationScope | None = None,
) -> Workbook:
    resolved_structure = structure or get_mosers_all_programs_output_structure()
    resolved_transformation_scope = (
        transformation_scope or get_mosers_all_programs_transformation_scope()
    )
    parsed = parser(raw_nisa_path)
    workbook = load_mosers_template_workbook()

    missing_sheets = [
        sheet for sheet in resolved_structure.required_sheets if sheet not in workbook.sheetnames
    ]
    if missing_sheets:
        missing = ", ".join(missing_sheets)
        raise ValueError(f"MOSERS template workbook missing required sheet(s): {missing}")

    worksheet = workbook[resolved_structure.cprs_ch_sheet]
    first_program = parsed.ch_rows[0].counterparty if parsed.ch_rows else ""
    worksheet[resolved_structure.program_name_cell] = first_program

    for transform in resolved_transformation_scope.cprs_ch_transforms:
        _write_vertical_values(
            worksheet=worksheet,
            column_letter=transform.target_column,
            start_row=resolved_structure.start_row,
            end_row=resolved_structure.end_row,
            values=_build_totals_metric_values(parsed.totals_rows, transform.source_metric),
        )

    plug_values_requirements = get_mosers_plug_values_mapping_requirements()
    for structure_mapping in plug_values_requirements.structure_mappings:
        _write_totals_rows_by_marker(
            worksheet=workbook[structure_mapping.target_sheet],
            totals_rows=parsed.totals_rows,
            section_marker=structure_mapping.section_marker,
            stop_markers=structure_mapping.stop_markers,
            field_mappings=structure_mapping.field_mappings,
        )

    return workbook


def _build_allocation_percentages(totals_rows: tuple[NisaTotalsRow, ...]) -> list[float]:
    total_notional = sum(row.notional for row in totals_rows)
    if total_notional == 0:
        return [0.0 for _ in totals_rows]
    return [row.notional / total_notional for row in totals_rows]


def _build_totals_metric_values(
    totals_rows: tuple[NisaTotalsRow, ...], source_metric: str
) -> list[float]:
    if source_metric == "annualized_volatility":
        return [row.annualized_volatility for row in totals_rows]
    if source_metric == "allocation_percentage":
        return _build_allocation_percentages(totals_rows)
    raise ValueError(f"Unsupported totals source metric: {source_metric}")


def _write_vertical_values(
    *,
    worksheet: Worksheet,
    column_letter: str,
    start_row: int,
    end_row: int,
    values: list[float],
) -> None:
    """Write values into a contiguous column range and clear remaining cells."""

    total_slots = (end_row - start_row) + 1
    for index in range(total_slots):
        row_number = start_row + index
        cell = f"{column_letter}{row_number}"
        worksheet[cell] = values[index] if index < len(values) else None


def _write_totals_rows_by_marker(
    *,
    worksheet: Worksheet,
    totals_rows: tuple[NisaTotalsRow, ...],
    section_marker: str,
    stop_markers: tuple[str, ...],
    field_mappings: tuple[MosersPlugValueFieldMapping, ...],
) -> None:
    marker_row = _find_marker_row(worksheet=worksheet, marker_text=section_marker)
    if marker_row is None:
        return

    start_row = marker_row + 1
    stop_row = _find_stop_row(worksheet=worksheet, start_row=start_row, stop_markers=stop_markers)
    end_row = (stop_row - 1) if stop_row is not None else int(worksheet.max_row)
    if end_row < start_row:
        return

    total_slots = (end_row - start_row) + 1
    for index in range(total_slots):
        row_number = start_row + index
        if index < len(totals_rows):
            _write_totals_row_values(
                worksheet=worksheet,
                row_number=row_number,
                row=totals_rows[index],
                field_mappings=field_mappings,
            )
            continue
        _clear_totals_row_values(
            worksheet=worksheet, row_number=row_number, field_mappings=field_mappings
        )


def _write_totals_row_values(
    *,
    worksheet: Worksheet,
    row_number: int,
    row: NisaTotalsRow,
    field_mappings: tuple[MosersPlugValueFieldMapping, ...],
) -> None:
    for mapping in field_mappings:
        worksheet[f"{mapping.target_column}{row_number}"] = _get_totals_row_field_value(
            row=row, source_field=mapping.source_field
        )


def _clear_totals_row_values(
    *,
    worksheet: Worksheet,
    row_number: int,
    field_mappings: tuple[MosersPlugValueFieldMapping, ...],
) -> None:
    for mapping in field_mappings:
        worksheet[f"{mapping.target_column}{row_number}"] = None


def _get_totals_row_field_value(*, row: NisaTotalsRow, source_field: str) -> Any:
    if not hasattr(row, source_field):
        raise ValueError(f"Unsupported plug-values source field: {source_field}")
    return getattr(row, source_field)


def _find_marker_row(*, worksheet: Worksheet, marker_text: str) -> int | None:
    marker = _normalize_marker_text(marker_text)
    for row_number in range(1, int(worksheet.max_row) + 1):
        cell_text = worksheet[f"{_SECTION_LABEL_COLUMN}{row_number}"].value
        if marker in _normalize_marker_text(cell_text):
            return row_number
    return None


def _find_stop_row(
    *, worksheet: Worksheet, start_row: int, stop_markers: tuple[str, ...]
) -> int | None:
    normalized_markers = tuple(_normalize_marker_text(marker) for marker in stop_markers)
    for row_number in range(start_row, int(worksheet.max_row) + 1):
        cell_text = _normalize_marker_text(worksheet[f"{_SECTION_LABEL_COLUMN}{row_number}"].value)
        if any(marker in cell_text for marker in normalized_markers):
            return row_number
    return None


def _normalize_marker_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip().casefold()
