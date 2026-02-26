from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from counter_risk.config import WorkflowConfig
from counter_risk.outputs import OutputContext
from counter_risk.outputs.pdf_export import PDFExportGenerator


def _minimal_config(tmp_path: Path, *, export_pdf: bool) -> WorkflowConfig:
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
        export_pdf=export_pdf,
    )


def _output_context(tmp_path: Path, *, export_pdf: bool) -> OutputContext:
    return OutputContext(
        config=_minimal_config(tmp_path, export_pdf=export_pdf),
        run_dir=tmp_path / "run",
        as_of_date=date(2026, 1, 31),
        run_date=date(2026, 2, 1),
    )


def test_pdf_export_generator_exports_when_com_is_available(tmp_path: Path) -> None:
    context = _output_context(tmp_path, export_pdf=True)
    source_pptx = context.run_dir / "distribution.pptx"
    source_pptx.parent.mkdir(parents=True, exist_ok=True)
    source_pptx.write_bytes(b"pptx")
    warnings: list[str] = []
    calls: list[tuple[Path, Path]] = []

    def _exporter(source: Path, output: Path) -> None:
        calls.append((source, output))
        output.write_bytes(b"pdf")

    generator = PDFExportGenerator(
        source_pptx=source_pptx,
        warnings=warnings,
        com_availability_checker=lambda: True,
        pptx_to_pdf_exporter=_exporter,
    )

    generated = generator.generate(context=context)

    expected_pdf = context.run_dir / "distribution.pdf"
    assert generated == (expected_pdf,)
    assert calls == [(source_pptx, expected_pdf)]
    assert warnings == []


def test_pdf_export_generator_warns_and_skips_when_com_unavailable(tmp_path: Path) -> None:
    context = _output_context(tmp_path, export_pdf=True)
    source_pptx = context.run_dir / "distribution.pptx"
    warnings: list[str] = []

    def _unexpected_export(_source: Path, _output: Path) -> None:
        raise AssertionError("exporter should not run when COM is unavailable")

    generator = PDFExportGenerator(
        source_pptx=source_pptx,
        warnings=warnings,
        com_availability_checker=lambda: False,
        pptx_to_pdf_exporter=_unexpected_export,
    )

    generated = generator.generate(context=context)

    assert generated == ()
    assert warnings == [
        "distribution_pdf requested but PowerPoint COM is unavailable; skipping PDF generation"
    ]


def test_pdf_export_generator_raises_when_export_fails(tmp_path: Path) -> None:
    context = _output_context(tmp_path, export_pdf=True)
    source_pptx = context.run_dir / "distribution.pptx"
    warnings: list[str] = []

    def _failing_export(_source: Path, _output: Path) -> None:
        raise RuntimeError("boom export")

    generator = PDFExportGenerator(
        source_pptx=source_pptx,
        warnings=warnings,
        com_availability_checker=lambda: True,
        pptx_to_pdf_exporter=_failing_export,
    )

    with pytest.raises(RuntimeError, match="PDF export failed: boom export"):
        generator.generate(context=context)
