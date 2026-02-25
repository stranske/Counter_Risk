"""Output generators for historical workbook updates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from counter_risk.calculations.wal import calculate_wal
from counter_risk.outputs.base import OutputContext, OutputGenerator
from counter_risk.writers.historical_update import append_wal_row, locate_ex_llc_3_year_workbook


class _WorkbookLocator(Protocol):
    def __call__(self) -> Path: ...


class _WalCalculator(Protocol):
    def __call__(self, exposure_summary_path: Path, px_date: date) -> float: ...


class _WalAppender(Protocol):
    def __call__(self, workbook_path: str | Path, *, px_date: date, wal_value: float) -> Path: ...


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
