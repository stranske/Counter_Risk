from __future__ import annotations

from pathlib import Path

from counter_risk.config import WorkflowConfig
from counter_risk.pipeline import run as run_module


def _make_minimal_config(
    tmp_path: Path,
    *,
    export_pdf: bool = False,
) -> WorkflowConfig:
    tmp_path.mkdir(parents=True, exist_ok=True)
    for name in (
        "all.xlsx",
        "ex.xlsx",
        "trend.xlsx",
        "hist_all.xlsx",
        "hist_ex.xlsx",
        "hist_llc.xlsx",
        "monthly.pptx",
    ):
        (tmp_path / name).write_bytes(b"placeholder")
    return WorkflowConfig(
        mosers_all_programs_xlsx=tmp_path / "all.xlsx",
        mosers_ex_trend_xlsx=tmp_path / "ex.xlsx",
        mosers_trend_xlsx=tmp_path / "trend.xlsx",
        hist_all_programs_3yr_xlsx=tmp_path / "hist_all.xlsx",
        hist_ex_llc_3yr_xlsx=tmp_path / "hist_ex.xlsx",
        hist_llc_3yr_xlsx=tmp_path / "hist_llc.xlsx",
        monthly_pptx=tmp_path / "monthly.pptx",
        export_pdf=export_pdf,
        output_root=tmp_path / "runs",
    )


class _FakeGenerator:
    name = "fake-pdf"

    def __init__(self, generated: tuple[Path, ...]) -> None:
        self._generated = generated

    def generate(self, *, context: object) -> tuple[Path, ...]:
        _ = context
        return self._generated


def test_export_distribution_pdf_returns_generated_path(tmp_path: Path, monkeypatch) -> None:
    source_pptx = tmp_path / "distribution.pptx"
    source_pptx.write_bytes(b"fake-pptx")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    config = _make_minimal_config(tmp_path / "cfg", export_pdf=True)
    pdf_path = run_dir / "distribution.pdf"

    monkeypatch.setattr(
        run_module,
        "_build_pdf_export_output_generator",
        lambda **_kwargs: _FakeGenerator((pdf_path,)),
    )

    result = run_module._export_distribution_pdf(
        source_pptx=source_pptx,
        run_dir=run_dir,
        config=config,
        as_of_date=config.as_of_date or run_module.date(2026, 2, 26),
        warnings=[],
    )

    assert result == pdf_path


def test_export_distribution_pdf_returns_none_when_generator_skips(
    tmp_path: Path, monkeypatch
) -> None:
    source_pptx = tmp_path / "distribution.pptx"
    source_pptx.write_bytes(b"fake-pptx")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    config = _make_minimal_config(tmp_path / "cfg", export_pdf=True)

    monkeypatch.setattr(
        run_module,
        "_build_pdf_export_output_generator",
        lambda **_kwargs: _FakeGenerator(()),
    )

    result = run_module._export_distribution_pdf(
        source_pptx=source_pptx,
        run_dir=run_dir,
        config=config,
        as_of_date=run_module.date(2026, 2, 26),
        warnings=[],
    )

    assert result is None
