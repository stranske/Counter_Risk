from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from counter_risk.config import WorkflowConfig
from counter_risk.outputs import (
    HistoricalWalWorkbookOutputGenerator,
    HistoricalWorkbookOutputGenerator,
    OutputContext,
)


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


def test_historical_workbook_generator_wraps_pipeline_historical_update_flow(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    output_context = _output_context(tmp_path)
    warnings: list[str] = []
    copied: list[tuple[Path, Path]] = []
    merged: list[tuple[Path, str, float, int]] = []
    expected_outputs = (
        run_dir / "hist_all.xlsx",
        run_dir / "hist_ex.xlsx",
        run_dir / "hist_llc.xlsx",
    )

    parsed_by_variant: dict[str, dict[str, object]] = {
        "all_programs": {"totals": [{"Notional": 100.0}]},
        "ex_trend": {"totals": [{"Notional": 200.0}]},
        "trend": {"totals": [{"Notional": 300.0}]},
    }

    def _fake_copy(src: str | Path, dst: str | Path, *, follow_symlinks: bool = True) -> str:
        del follow_symlinks
        source = Path(src)
        target = Path(dst)
        copied.append((source, target))
        target.write_bytes(source.read_bytes())
        return str(target)

    def _fake_records(table: Any) -> list[dict[str, object]]:
        return [dict(record) for record in table]

    def _fake_merge(
        *,
        workbook_path: Path,
        variant: str,
        as_of_date: date,
        totals_records: list[dict[str, object]],
        warnings: list[str],
    ) -> None:
        del warnings
        merged.append(
            (workbook_path, variant, float(totals_records[0]["Notional"]), as_of_date.month)
        )

    generator = HistoricalWorkbookOutputGenerator(
        parsed_by_variant=parsed_by_variant,
        warnings=warnings,
        workbook_copier=_fake_copy,
        records_extractor=_fake_records,
        workbook_merger=_fake_merge,
    )

    generated = generator.generate(context=output_context)

    assert generator.name == "historical_workbook"
    assert generated == expected_outputs
    assert [target for _, target in copied] == list(expected_outputs)
    assert merged == [
        (expected_outputs[0], "all_programs", 100.0, 1),
        (expected_outputs[1], "ex_trend", 200.0, 1),
        (expected_outputs[2], "trend", 300.0, 1),
    ]
