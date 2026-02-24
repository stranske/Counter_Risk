"""Integration-style pipeline output tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from zipfile import ZipFile

import pytest

import counter_risk.pipeline.run as run_module
from counter_risk.config import WorkflowConfig
from counter_risk.pipeline.ppt_naming import resolve_ppt_output_names
from counter_risk.pipeline.ppt_validation import PptStandaloneValidationResult


def _write_placeholder(path: Path, *, payload: bytes = b"fixture") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _read_media_payloads(pptx_path: Path) -> dict[str, bytes]:
    with ZipFile(pptx_path) as archive:
        return {
            name: archive.read(name)
            for name in archive.namelist()
            if name.startswith("ppt/media/") and not name.endswith("/")
        }


def _build_config(tmp_path: Path, screenshot_inputs: dict[str, Path]) -> WorkflowConfig:
    inputs_dir = tmp_path / "inputs"
    files = {
        "all_programs": inputs_dir / "all_programs.xlsx",
        "ex_trend": inputs_dir / "ex_trend.xlsx",
        "trend": inputs_dir / "trend.xlsx",
        "hist_all": inputs_dir / "hist_all.xlsx",
        "hist_ex": inputs_dir / "hist_ex.xlsx",
        "hist_llc": inputs_dir / "hist_llc.xlsx",
    }
    for path in files.values():
        _write_placeholder(path)

    return WorkflowConfig(
        mosers_all_programs_xlsx=files["all_programs"],
        mosers_ex_trend_xlsx=files["ex_trend"],
        mosers_trend_xlsx=files["trend"],
        hist_all_programs_3yr_xlsx=files["hist_all"],
        hist_ex_llc_3yr_xlsx=files["hist_ex"],
        hist_llc_3yr_xlsx=files["hist_llc"],
        monthly_pptx=Path("tests/fixtures/Monthly Counterparty Exposure Report.pptx"),
        output_root=tmp_path / "ignored-output-root",
        enable_screenshot_replacement=True,
        screenshot_replacement_implementation="zip",
        screenshot_inputs=screenshot_inputs,
    )


def test_write_outputs_screenshot_replacement_replaces_expected_number_of_media_parts(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)

    screenshot_inputs = {
        "slide1": Path("tests/fixtures/screenshots/slide_1.png"),
        "slide2": Path("tests/fixtures/screenshots/slide_2.png"),
    }
    config = _build_config(tmp_path, screenshot_inputs)

    source_ppt = config.monthly_pptx
    input_media = _read_media_payloads(source_ppt)

    as_of_date = date(2025, 12, 31)
    output_paths, _ = run_module._write_outputs(
        run_dir=run_dir,
        config=config,
        as_of_date=as_of_date,
        warnings=[],
    )
    output_names = resolve_ppt_output_names(as_of_date)
    output_ppt = run_dir / output_names.master_filename
    distribution_ppt = run_dir / output_names.distribution_filename

    assert output_ppt in output_paths
    assert distribution_ppt in output_paths
    assert output_ppt.exists()
    assert distribution_ppt.exists()
    assert output_ppt.read_bytes() != source_ppt.read_bytes()

    output_media = _read_media_payloads(output_ppt)
    changed_media_parts = sorted(
        name for name, payload in output_media.items() if input_media.get(name) != payload
    )
    assert len(changed_media_parts) == len(screenshot_inputs)


def test_write_outputs_skips_all_ppt_generation_when_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    config = _build_config(tmp_path, screenshot_inputs={})
    config = config.model_copy(update={"enable_ppt_output": False})

    def _unexpected_call(*args: object, **kwargs: object) -> None:
        raise AssertionError("PPT generation should not be called when PPT output is disabled")

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


def test_write_outputs_skips_distribution_when_master_refresh_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    config = _build_config(tmp_path, screenshot_inputs={})
    config = config.model_copy(update={"enable_screenshot_replacement": False})
    called: dict[str, int] = {"derive_distribution": 0}
    warnings: list[str] = []

    def _refresh(_path: Path) -> run_module.PptProcessingResult:
        return run_module.PptProcessingResult(
            status=run_module.PptProcessingStatus.FAILED,
            error_detail="forced refresh failure",
        )

    def _derive_distribution(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        called["derive_distribution"] += 1

    monkeypatch.setattr(run_module, "_refresh_ppt_links", _refresh)
    monkeypatch.setattr(run_module, "_derive_distribution_ppt", _derive_distribution)

    as_of_date = date(2025, 12, 31)
    output_names = resolve_ppt_output_names(as_of_date)
    output_paths, ppt_result = run_module._write_outputs(
        run_dir=run_dir,
        config=config,
        as_of_date=as_of_date,
        warnings=warnings,
    )

    assert ppt_result.status == run_module.PptProcessingStatus.FAILED
    assert called["derive_distribution"] == 0
    assert any("PPT links refresh failed; forced refresh failure" in w for w in warnings)
    assert (run_dir / output_names.master_filename) in output_paths
    assert (run_dir / output_names.distribution_filename) not in output_paths
    assert not (run_dir / output_names.distribution_filename).exists()


def test_write_outputs_handles_master_refresh_exception_and_logs_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("ERROR")
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    config = _build_config(tmp_path, screenshot_inputs={})
    config = config.model_copy(update={"enable_screenshot_replacement": False})
    called: dict[str, int] = {"derive_distribution": 0}

    def _refresh_raises(_path: Path) -> run_module.PptProcessingResult:
        raise RuntimeError("refresh exploded")

    def _derive_distribution(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        called["derive_distribution"] += 1

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
    assert called["derive_distribution"] == 0
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


def test_write_outputs_raises_when_distribution_standalone_validation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    config = _build_config(tmp_path, screenshot_inputs={})
    config = config.model_copy(update={"enable_screenshot_replacement": False})
    called: dict[str, int] = {"validate_distribution": 0}

    def _refresh(_path: Path) -> run_module.PptProcessingResult:
        return run_module.PptProcessingResult(status=run_module.PptProcessingStatus.SUCCESS)

    def _validate_distribution(_path: Path) -> PptStandaloneValidationResult:
        called["validate_distribution"] += 1
        return PptStandaloneValidationResult(
            is_valid=False,
            external_relationship_count=1,
            relationship_parts_scanned=("ppt/slides/_rels/slide1.xml.rels",),
            external_relationship_parts=("ppt/slides/_rels/slide1.xml.rels",),
        )

    monkeypatch.setattr(run_module, "_refresh_ppt_links", _refresh)
    monkeypatch.setattr(run_module, "validate_distribution_ppt_standalone", _validate_distribution)

    with pytest.raises(RuntimeError, match="Distribution PPT standalone validation failed"):
        run_module._write_outputs(
            run_dir=run_dir,
            config=config,
            as_of_date=date(2025, 12, 31),
            warnings=[],
        )

    assert called["validate_distribution"] == 1
