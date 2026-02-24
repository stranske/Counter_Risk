"""Targeted PPT output tests for pipeline acceptance criteria."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

import counter_risk.pipeline.run as run_module
from counter_risk.config import WorkflowConfig


def _write_placeholder(path: Path, *, payload: bytes = b"fixture") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _build_config(tmp_path: Path, *, enable_ppt_output: bool) -> WorkflowConfig:
    inputs_dir = tmp_path / "inputs"
    files = {
        "all_programs": inputs_dir / "all_programs.xlsx",
        "ex_trend": inputs_dir / "ex_trend.xlsx",
        "trend": inputs_dir / "trend.xlsx",
        "hist_all": inputs_dir / "hist_all.xlsx",
        "hist_ex": inputs_dir / "hist_ex.xlsx",
        "hist_llc": inputs_dir / "hist_llc.xlsx",
    }
    for input_path in files.values():
        _write_placeholder(input_path)

    return WorkflowConfig(
        mosers_all_programs_xlsx=files["all_programs"],
        mosers_ex_trend_xlsx=files["ex_trend"],
        mosers_trend_xlsx=files["trend"],
        hist_all_programs_3yr_xlsx=files["hist_all"],
        hist_ex_llc_3yr_xlsx=files["hist_ex"],
        hist_llc_3yr_xlsx=files["hist_llc"],
        monthly_pptx=Path("tests/fixtures/Monthly Counterparty Exposure Report.pptx"),
        output_root=tmp_path / "ignored-output-root",
        enable_screenshot_replacement=False,
        enable_ppt_output=enable_ppt_output,
    )


def test_ppt_disabled_skips_ppt_entrypoint_and_produces_no_pptx(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    config = _build_config(tmp_path, enable_ppt_output=False)

    def _unexpected_call(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise AssertionError("PPT code path should not be called when PPT output is disabled")

    monkeypatch.setattr(run_module, "_get_screenshot_replacer", _unexpected_call)
    monkeypatch.setattr(run_module, "_refresh_ppt_links", _unexpected_call)
    monkeypatch.setattr(run_module, "_derive_distribution_ppt", _unexpected_call)

    output_paths, ppt_result = run_module._write_outputs(
        run_dir=run_dir,
        config=config,
        as_of_date=date(2025, 12, 31),
        warnings=[],
    )

    assert ppt_result.status == run_module.PptProcessingStatus.SKIPPED
    assert all(path.suffix.lower() != ".pptx" for path in output_paths)
    assert list(run_dir.glob("*.pptx")) == []


def test_ppt_enabled_names_produce_exactly_two_expected_pptx_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    config = _build_config(tmp_path, enable_ppt_output=True)

    monkeypatch.setattr(
        run_module,
        "_refresh_ppt_links",
        lambda _path: run_module.PptProcessingResult(status=run_module.PptProcessingStatus.SUCCESS),
    )
    run_module._write_outputs(
        run_dir=run_dir,
        config=config,
        as_of_date=date(2025, 12, 31),
        warnings=[],
    )

    assert sorted(path.name for path in run_dir.glob("*.pptx")) == [
        "Monthly Counterparty Exposure Report (Master) - 2025-12-31.pptx",
        "Monthly Counterparty Exposure Report - 2025-12-31.pptx",
    ]


def test_master_refresh_failure_logs_error_and_skips_distribution_derivation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("ERROR")
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    config = _build_config(tmp_path, enable_ppt_output=True)
    calls = {"distribution": 0}

    def _refresh_raises(_path: Path) -> run_module.PptProcessingResult:
        raise RuntimeError("refresh exploded")

    def _derive_distribution(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        calls["distribution"] += 1

    monkeypatch.setattr(run_module, "_refresh_ppt_links", _refresh_raises)
    monkeypatch.setattr(run_module, "_derive_distribution_ppt", _derive_distribution)

    output_paths, ppt_result = run_module._write_outputs(
        run_dir=run_dir,
        config=config,
        as_of_date=date(2025, 12, 31),
        warnings=[],
    )

    assert ppt_result.status == run_module.PptProcessingStatus.FAILED
    assert "refresh exploded" in (ppt_result.error_detail or "")
    assert calls["distribution"] == 0
    assert any(
        "Master" in record.message
        and "PPT" in record.message
        and "refresh exploded" in record.message
        for record in caplog.records
        if record.levelname == "ERROR"
    )
    assert all(
        path.name != "Monthly Counterparty Exposure Report - 2025-12-31.pptx"
        for path in output_paths
    )
