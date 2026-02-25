"""Output generators for historical workbook updates."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Protocol

from counter_risk.calculations.wal import calculate_wal
from counter_risk.outputs.base import OutputContext, OutputGenerator
from counter_risk.pipeline.run import _merge_historical_workbook, _records
from counter_risk.writers.historical_update import append_wal_row, locate_ex_llc_3_year_workbook


class _WorkbookLocator(Protocol):
    def __call__(self) -> Path: ...


class _WalCalculator(Protocol):
    def __call__(self, exposure_summary_path: Path, px_date: date) -> float: ...


class _WalAppender(Protocol):
    def __call__(self, workbook_path: str | Path, *, px_date: date, wal_value: float) -> Path: ...


class _WorkbookCopier(Protocol):
    def __call__(
        self, src: str | Path, dst: str | Path, *, follow_symlinks: bool = True
    ) -> str: ...


class _HistoricalWorkbookMerger(Protocol):
    def __call__(
        self,
        *,
        workbook_path: Path,
        variant: str,
        as_of_date: date,
        totals_records: list[dict[str, Any]],
        warnings: list[str],
    ) -> None: ...


class _RecordsExtractor(Protocol):
    def __call__(self, table: Any) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class HistoricalWorkbookOutputGenerator(OutputGenerator):
    """Generate historical workbook outputs for all reporting variants."""

    parsed_by_variant: Mapping[str, Mapping[str, Any]]
    warnings: list[str]
    name: str = "historical_workbook"
    workbook_copier: _WorkbookCopier = shutil.copy2
    workbook_merger: _HistoricalWorkbookMerger = _merge_historical_workbook
    records_extractor: _RecordsExtractor = _records

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
        for variant, _workbook_path, historical_path in variant_inputs:
            target_hist = context.run_dir / historical_path.name
            self.workbook_copier(historical_path, target_hist)
            totals_records = self.records_extractor(self.parsed_by_variant[variant]["totals"])
            self.workbook_merger(
                workbook_path=target_hist,
                variant=variant,
                as_of_date=context.as_of_date,
                totals_records=totals_records,
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
