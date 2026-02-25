from __future__ import annotations

from datetime import date
from pathlib import Path

from counter_risk.config import WorkflowConfig
from counter_risk.outputs import HistoricalWalWorkbookOutputGenerator, OutputContext


def _minimal_config(tmp_path: Path) -> WorkflowConfig:
    for filename in (
        "all.xlsx",
        "ex.xlsx",
        "trend.xlsx",
        "hist_all.xlsx",
        "hist_ex.xlsx",
        "hist_llc.xlsx",
        "monthly.pptx",
    ):
        (tmp_path / filename).write_bytes(b"placeholder")

    return WorkflowConfig(
        mosers_all_programs_xlsx=tmp_path / "all.xlsx",
        mosers_ex_trend_xlsx=tmp_path / "ex.xlsx",
        mosers_trend_xlsx=tmp_path / "trend.xlsx",
        hist_all_programs_3yr_xlsx=tmp_path / "hist_all.xlsx",
        hist_ex_llc_3yr_xlsx=tmp_path / "hist_ex.xlsx",
        hist_llc_3yr_xlsx=tmp_path / "hist_llc.xlsx",
        monthly_pptx=tmp_path / "monthly.pptx",
    )


def _output_context(tmp_path: Path) -> OutputContext:
    return OutputContext(
        config=_minimal_config(tmp_path),
        run_dir=tmp_path / "run",
        as_of_date=date(2026, 1, 31),
        run_date=date(2026, 2, 1),
    )


def test_historical_wal_generator_delegates_to_existing_wal_update_flow(tmp_path: Path) -> None:
    exposure_summary_path = tmp_path / "exposure-summary.xlsx"
    exposure_summary_path.write_bytes(b"placeholder")
    workbook_path = tmp_path / "historical.xlsx"
    workbook_path.write_bytes(b"placeholder")
    calls: list[tuple[str, object, object]] = []

    def _fake_locate() -> Path:
        calls.append(("locate", None, None))
        return workbook_path

    def _fake_calculate(path: Path, px_date: date) -> float:
        calls.append(("calculate_wal", path, px_date))
        return 2.718

    def _fake_append(path: str | Path, *, px_date: date, wal_value: float) -> Path:
        calls.append(("append_wal_row", Path(path), (px_date, wal_value)))
        return Path(path)

    generator = HistoricalWalWorkbookOutputGenerator(
        exposure_summary_path=exposure_summary_path,
        workbook_locator=_fake_locate,
        wal_calculator=_fake_calculate,
        wal_appender=_fake_append,
    )

    generated = generator.generate(context=_output_context(tmp_path))

    assert generator.name == "historical_wal_workbook"
    assert generated == (workbook_path,)
    assert calls == [
        ("locate", None, None),
        ("calculate_wal", exposure_summary_path, date(2026, 1, 31)),
        ("append_wal_row", workbook_path, (date(2026, 1, 31), 2.718)),
    ]


def test_historical_wal_generator_uses_explicit_workbook_path_when_provided(tmp_path: Path) -> None:
    exposure_summary_path = tmp_path / "exposure-summary.xlsx"
    exposure_summary_path.write_bytes(b"placeholder")
    workbook_path = tmp_path / "historical.xlsx"
    workbook_path.write_bytes(b"placeholder")

    locate_calls: list[str] = []

    def _fake_locate() -> Path:
        locate_calls.append("called")
        return tmp_path / "unexpected.xlsx"

    def _fake_calculate(path: Path, px_date: date) -> float:
        del path, px_date
        return 1.23

    def _fake_append(path: str | Path, *, px_date: date, wal_value: float) -> Path:
        del px_date, wal_value
        return Path(path)

    generator = HistoricalWalWorkbookOutputGenerator(
        exposure_summary_path=exposure_summary_path,
        workbook_path=workbook_path,
        workbook_locator=_fake_locate,
        wal_calculator=_fake_calculate,
        wal_appender=_fake_append,
    )

    generated = generator.generate(context=_output_context(tmp_path))

    assert generated == (workbook_path,)
    assert locate_calls == []
