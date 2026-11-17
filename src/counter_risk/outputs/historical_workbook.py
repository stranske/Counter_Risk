"""Output generators for historical workbook updates."""

from __future__ import annotations

import logging
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, cast

from counter_risk.calculations.wal import calculate_wal
from counter_risk.outputs.base import OutputContext, OutputGenerator
from counter_risk.parsers.cprs_ch import (
    ClassNotionalBreakdown,
    read_class_notional_breakdown_with_provenance,
)
from counter_risk.writers.historical_update import append_wal_row, locate_ex_llc_3_year_workbook

_WorkbookLocator = Callable[[], Path]
_WalCalculator = Callable[[Path, date], float]
_WalAppender = Callable[..., Path]
_WorkbookCopier = Callable[[str | Path, str | Path], str]
_HistoricalWorkbookMerger = Callable[..., None]
_RecordsExtractor = Callable[[Any], list[dict[str, Any]]]
_ClassBreakdownReader = Callable[[Path], ClassNotionalBreakdown | dict[str, float] | None]
LOGGER = logging.getLogger(__name__)


def warn_class_breakdown(
    *, variant: str, source: str, coerced_invalid_cells: int, warnings: list[str]
) -> None:
    """Report class-share degradation once, including for direct merger callers."""
    messages: list[str] = []
    if source == "record-derived":
        messages.append(
            f"CLASS_BREAKDOWN_FALLBACK: {variant} uses record-derived fallback shares; "
            "published class notional breakdown unavailable"
        )
    elif variant == "trend" and source != "absolute":
        messages.append(
            f"CLASS_BREAKDOWN_FALLBACK: trend uses {source} class notional breakdown; "
            "absolute-value breakdown unavailable"
        )
    if coerced_invalid_cells > 0:
        messages.append(
            f"CLASS_BREAKDOWN_CELL_COERCED: {variant} class notional breakdown has "
            f"{coerced_invalid_cells} invalid cell(s) coerced to zero"
        )
    for message in messages:
        if message not in warnings:
            warnings.append(message)


@dataclass(frozen=True)
class HistoricalWorkbookOutputGenerator(OutputGenerator):
    """Generate historical workbook outputs for all reporting variants."""

    parsed_by_variant: Mapping[str, Mapping[str, Any]]
    warnings: list[str]
    workbook_merger: _HistoricalWorkbookMerger
    records_extractor: _RecordsExtractor
    name: str = "historical_workbook"
    workbook_copier: _WorkbookCopier = cast(_WorkbookCopier, shutil.copy2)
    class_breakdown_reader: _ClassBreakdownReader = read_class_notional_breakdown_with_provenance
    class_breakdown_sources: dict[str, str] = field(default_factory=dict)

    def generate(self, *, context: OutputContext) -> tuple[Path, ...]:
        mosers_all_programs = context.config.mosers_all_programs_xlsx
        if mosers_all_programs is None:
            raise ValueError("mosers_all_programs_xlsx is required for pipeline execution")

        variant_inputs = (
            ("all_programs", mosers_all_programs, context.config.hist_all_programs_3yr_xlsx),
            ("ex_trend", context.config.mosers_ex_trend_xlsx, context.config.hist_ex_llc_3yr_xlsx),
            ("trend", context.config.mosers_trend_xlsx, context.config.hist_llc_3yr_xlsx),
        )

        output_paths: list[Path] = []
        for variant, source_workbook_path, historical_path in variant_inputs:
            target_hist = context.run_dir / historical_path.name
            self.workbook_copier(historical_path, target_hist)
            variant_sections = self.parsed_by_variant[variant]
            cprs_ch_records = self.records_extractor(variant_sections["cprs_ch"])
            # The CPRS-CH tab publishes the asset-class mix directly; for Trend that
            # is an absolute-value row that cannot be reconstructed from the parsed
            # clearing-house rows. Read it here and let the merger prefer it.
            result: ClassNotionalBreakdown | dict[str, float] | None = None
            if source_workbook_path is not None:
                try:
                    result = self.class_breakdown_reader(source_workbook_path)
                except Exception as exc:
                    LOGGER.warning(
                        "Class notional breakdown unavailable for %s; "
                        "falling back to record-derived shares (%s)",
                        variant,
                        exc,
                    )
            class_breakdown: dict[str, float] | None
            if isinstance(result, ClassNotionalBreakdown):
                class_breakdown = result.values
                source = result.source if class_breakdown else "record-derived"
                coerced_invalid_cells = result.coerced_invalid_cells
            else:
                class_breakdown = result
                source = "plain" if class_breakdown else "record-derived"
                coerced_invalid_cells = 0
            self.class_breakdown_sources[variant] = source
            warn_class_breakdown(
                variant=variant,
                source=source,
                coerced_invalid_cells=coerced_invalid_cells,
                warnings=self.warnings,
            )
            self.workbook_merger(
                workbook_path=target_hist,
                variant=variant,
                as_of_date=context.as_of_date,
                cprs_ch_records=cprs_ch_records,
                formatting_profile=context.formatting_profile,
                class_breakdown=class_breakdown,
                class_breakdown_source=source,
                coerced_invalid_cells=coerced_invalid_cells,
                warnings=self.warnings,
            )
            output_paths.append(target_hist)

        return tuple(output_paths)


@dataclass(frozen=True)
class HistoricalWalWorkbookOutputGenerator(OutputGenerator):
    """Generate the historical WAL workbook update output."""

    exposure_summary_path: Path
    name: str = "historical_wal_workbook"
    workbook_path: Path | None = None
    workbook_locator: _WorkbookLocator = locate_ex_llc_3_year_workbook
    wal_calculator: _WalCalculator = calculate_wal
    wal_appender: _WalAppender = append_wal_row

    def generate(self, *, context: OutputContext) -> tuple[Path, ...]:
        workbook_path = self.workbook_path or self.workbook_locator()
        wal_value = self.wal_calculator(self.exposure_summary_path, context.as_of_date)
        updated_workbook = self.wal_appender(
            workbook_path,
            px_date=context.as_of_date,
            wal_value=wal_value,
        )
        return (updated_workbook,)
