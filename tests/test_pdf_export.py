from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from counter_risk.config import WorkflowConfig
from counter_risk.pipeline import run as run_module


def _make_minimal_config(
    tmp_path: Path,
    *,
    distribution_static: bool = False,
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
        distribution_static=distribution_static,
        export_pdf=export_pdf,
        output_root=tmp_path / "runs",
    )


def test_export_distribution_pdf_raises_and_logs_when_export_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr("counter_risk.pipeline.run.platform.system", lambda: "Windows")

    source_pptx = tmp_path / "distribution.pptx"
    source_pptx.write_bytes(b"fake-pptx")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    config = _make_minimal_config(tmp_path / "cfg", export_pdf=True)

    class _FakePresentation:
        def ExportAsFixedFormat(self, _path: str, _fmt: int) -> None:  # noqa: N802
            raise RuntimeError("boom export")

        def Close(self) -> None:  # noqa: N802
            return None

    class _FakePowerPointApplication:
        def __init__(self) -> None:
            self.Visible = False
            self.Presentations = types.SimpleNamespace(
                Open=lambda *_args, **_kwargs: _FakePresentation()
            )

        def Quit(self) -> None:  # noqa: N802
            return None

    fake_client = types.SimpleNamespace(
        DispatchEx=lambda *_args, **_kwargs: _FakePowerPointApplication()
    )
    fake_win32com = types.ModuleType("win32com")
    fake_win32com.client = fake_client
    monkeypatch.setitem(sys.modules, "win32com", fake_win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", fake_client)

    with pytest.raises(RuntimeError, match="PDF export failed: boom export"):
        run_module._export_distribution_pdf(
            source_pptx=source_pptx,
            run_dir=run_dir,
            config=config,
        )

    assert "PDF export failed" in caplog.text
    assert "boom export" in caplog.text


def test_export_distribution_pdf_skips_when_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    source_pptx = tmp_path / "distribution.pptx"
    source_pptx.write_bytes(b"fake-pptx")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    config = _make_minimal_config(tmp_path / "cfg", export_pdf=False)

    def _fail_if_called(*, source_pptx: Path, pdf_path: Path) -> None:
        raise AssertionError(f"exporter should not be called for {source_pptx} -> {pdf_path}")

    monkeypatch.setattr(run_module, "_export_pptx_to_pdf", _fail_if_called)

    result = run_module._export_distribution_pdf(
        source_pptx=source_pptx,
        run_dir=run_dir,
        config=config,
    )

    assert result is None
    assert "distribution_pdf_skipped reason=export_pdf_disabled" in caplog.text
