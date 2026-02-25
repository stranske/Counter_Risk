"""Targeted PPT output tests for pipeline acceptance criteria."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest

import counter_risk.pipeline.run as run_module
from counter_risk.config import WorkflowConfig
from counter_risk.pipeline.manifest import ManifestBuilder
from counter_risk.pipeline.ppt_validation import PptStandaloneValidationResult


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


def test_ppt_enabled_order_master_generated_before_distribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    config = _build_config(tmp_path, enable_ppt_output=True)
    config.enable_screenshot_replacement = True

    call_order: list[str] = []

    def _replace_master(source: Path, target: Path, screenshot_inputs: dict[str, Path]) -> None:
        _ = screenshot_inputs
        call_order.append("master_generation")
        shutil.copy2(source, target)

    def _refresh_links(_path: Path) -> run_module.PptProcessingResult:
        call_order.append("master_refresh")
        return run_module.PptProcessingResult(status=run_module.PptProcessingStatus.SUCCESS)

    def _derive_distribution(*, master_pptx_path: Path, distribution_pptx_path: Path) -> None:
        call_order.append("distribution_derivation")
        shutil.copy2(master_pptx_path, distribution_pptx_path)

    monkeypatch.setattr(run_module, "_resolve_screenshot_input_mapping", lambda _config: {})
    monkeypatch.setattr(run_module, "_get_screenshot_replacer", lambda _impl: _replace_master)
    monkeypatch.setattr(run_module, "_refresh_ppt_links", _refresh_links)
    monkeypatch.setattr(run_module, "_derive_distribution_ppt", _derive_distribution)
    monkeypatch.setattr(
        run_module,
        "validate_distribution_ppt_standalone",
        lambda _path: PptStandaloneValidationResult(
            is_valid=True,
            external_relationship_count=0,
            relationship_parts_scanned=(),
            external_relationship_parts=(),
        ),
    )

    run_module._write_outputs(
        run_dir=run_dir,
        config=config,
        as_of_date=date(2025, 12, 31),
        warnings=[],
    )

    assert call_order.index("master_generation") < call_order.index("distribution_derivation")
    assert call_order.count("distribution_derivation") == 1


def test_no_distribution_without_master_when_master_generation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    config = _build_config(tmp_path, enable_ppt_output=True)
    as_of_date = date(2025, 12, 31)
    distribution_name = f"Monthly Counterparty Exposure Report - {as_of_date.isoformat()}.pptx"

    def _refresh_raises(_path: Path) -> run_module.PptProcessingResult:
        raise RuntimeError("refresh exploded")

    monkeypatch.setattr(run_module, "_refresh_ppt_links", _refresh_raises)

    output_paths, _ppt_result = run_module._write_outputs(
        run_dir=run_dir,
        config=config,
        as_of_date=as_of_date,
        warnings=[],
    )

    assert not (run_dir / distribution_name).exists()
    assert not (run_dir / "README.txt").exists()

    manifest = ManifestBuilder(
        config=config,
        as_of_date=as_of_date,
        run_date=date(2026, 1, 2),
    ).build(
        run_dir=run_dir,
        input_hashes={},
        output_paths=output_paths,
        top_exposures={},
        top_changes_per_variant={},
        warnings=[],
        ppt_status=run_module.PptProcessingStatus.FAILED.value,
    )
    assert all(Path(path).name != distribution_name for path in manifest["output_paths"])
    assert all(Path(path).name != "README.txt" for path in manifest["output_paths"])
    assert "distribution" not in manifest.get("ppt_outputs", {})
