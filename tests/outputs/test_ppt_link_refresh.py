from __future__ import annotations

from datetime import date
from pathlib import Path

from counter_risk.config import WorkflowConfig
from counter_risk.outputs import (
    OutputContext,
    PptLinkRefreshOutputGenerator,
    PptLinkRefreshResult,
    PptLinkRefreshStatus,
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


def test_ppt_link_refresh_generator_runs_refresher_and_records_success(tmp_path: Path) -> None:
    context = _output_context(tmp_path)
    warnings: list[str] = []
    seen: dict[str, Path] = {}

    def _refresh(pptx_path: Path) -> object:
        seen["path"] = pptx_path
        return PptLinkRefreshResult(status=PptLinkRefreshStatus.SUCCESS)

    generator = PptLinkRefreshOutputGenerator(
        warnings=warnings,
        ppt_link_refresher=_refresh,
    )

    generated = generator.generate(context=context)

    assert generated == ()
    assert seen["path"] == (
        context.run_dir / "Monthly Counterparty Exposure Report (Master) - 2026-01-31.pptx"
    )
    assert generator.last_result == PptLinkRefreshResult(status=PptLinkRefreshStatus.SUCCESS)
    assert warnings == []


def test_ppt_link_refresh_generator_interprets_false_as_skipped(tmp_path: Path) -> None:
    context = _output_context(tmp_path)
    warnings: list[str] = []

    generator = PptLinkRefreshOutputGenerator(
        warnings=warnings,
        ppt_link_refresher=lambda _pptx_path: False,
    )

    generator.generate(context=context)

    assert generator.last_result == PptLinkRefreshResult(status=PptLinkRefreshStatus.SKIPPED)
    assert warnings == ["PPT links not refreshed; COM refresh skipped"]


def test_ppt_link_refresh_generator_captures_refresh_exceptions(tmp_path: Path) -> None:
    context = _output_context(tmp_path)
    warnings: list[str] = []

    def _refresh(_pptx_path: Path) -> object:
        raise RuntimeError("forced refresh failure")

    generator = PptLinkRefreshOutputGenerator(
        warnings=warnings,
        ppt_link_refresher=_refresh,
    )

    generator.generate(context=context)

    assert generator.last_result == PptLinkRefreshResult(
        status=PptLinkRefreshStatus.FAILED,
        error_detail="forced refresh failure",
    )
    assert warnings == ["PPT links refresh failed; forced refresh failure"]
