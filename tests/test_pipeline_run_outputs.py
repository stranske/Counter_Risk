"""Integration-style pipeline output tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from zipfile import ZipFile

import pytest

import counter_risk.pipeline.run as run_module
from counter_risk.config import OutputGeneratorConfig, WorkflowConfig
from counter_risk.outputs.base import OutputContext
from counter_risk.pipeline.ppt_naming import resolve_ppt_output_names
from counter_risk.pipeline.ppt_validation import PptStandaloneValidationResult


class _ConfigRegisteredOutputGenerator:
    name = "config_registered_output"

    def generate(self, *, context: OutputContext) -> tuple[Path, ...]:
        output_path = context.run_dir / "config-registered-output.txt"
        output_path.write_text("ok", encoding="utf-8")
        return (output_path,)


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


def test_write_outputs_generates_all_programs_dropin_when_template_is_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    config = _build_config(tmp_path, screenshot_inputs={}).model_copy(
        update={
            "enable_ppt_output": False,
            "dropin_all_programs_template_xlsx": tmp_path / "inputs" / "dropin-template.xlsx",
        }
    )
    config.dropin_all_programs_template_xlsx.write_bytes(b"fixture")
    warnings: list[str] = []
    observed: dict[str, object] = {}

    def _fake_fill_dropin_template(
        template_path: Path,
        exposures_df: object,
        breakdown: object,
        *,
        output_path: Path,
        repo_cash_by_counterparty: object | None = None,
    ) -> Path:
        observed["template_path"] = template_path
        observed["exposures"] = exposures_df
        observed["breakdown"] = breakdown
        observed["repo_cash_by_counterparty"] = repo_cash_by_counterparty
        output_path.write_bytes(b"filled-dropin")
        return output_path

    monkeypatch.setattr(run_module, "fill_dropin_template", _fake_fill_dropin_template)

    parsed_by_variant: dict[str, dict[str, object]] = {
        "all_programs": {
            "totals": [
                {
                    "counterparty": "CIBC",
                    "Cash": 125.0,
                    "TIPS": 25.0,
                    "Treasury": 50.0,
                    "Equity": 75.0,
                    "Commodity": 10.0,
                    "Currency": 5.0,
                    "Notional": 265.0,
                    "NotionalChange": 12.0,
                }
            ],
            "futures": [],
        }
    }

    output_paths, ppt_result = run_module._write_outputs(
        run_dir=run_dir,
        config=config,
        as_of_date=date(2025, 12, 31),
        warnings=warnings,
        parsed_by_variant=parsed_by_variant,
    )

    expected_dropin = run_dir / "dropin-filled.xlsx"
    assert ppt_result.status == run_module.PptProcessingStatus.SKIPPED
    assert expected_dropin in output_paths
    assert expected_dropin.exists()
    assert observed["template_path"] == config.dropin_all_programs_template_xlsx
    assert observed["exposures"] == parsed_by_variant["all_programs"]["totals"]
    assert observed["repo_cash_by_counterparty"] is None
    assert observed["breakdown"] == {
        "tips": pytest.approx(25.0 / 265.0),
        "treasury": pytest.approx(50.0 / 265.0),
        "equity": pytest.approx(75.0 / 265.0),
        "commodity": pytest.approx(10.0 / 265.0),
        "currency": pytest.approx(5.0 / 265.0),
        "notional": pytest.approx(1.0),
    }
    assert "Generated All Programs Drop-In output workbook" in warnings


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


def test_write_outputs_skips_disabled_refresh_generator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    config = _build_config(tmp_path, screenshot_inputs={})
    config = config.model_copy(
        update={
            "enable_screenshot_replacement": False,
            "output_generators": tuple(
                entry
                for entry in config.output_generators
                if entry.name in {"ppt_screenshot", "pdf_export"}
            ),
        }
    )
    called: dict[str, int] = {"refresh": 0}

    def _unexpected_refresh(_path: Path) -> run_module.PptProcessingResult:
        called["refresh"] += 1
        return run_module.PptProcessingResult(status=run_module.PptProcessingStatus.SUCCESS)

    monkeypatch.setattr(run_module, "_refresh_ppt_links", _unexpected_refresh)

    output_paths, _ppt_result = run_module._write_outputs(
        run_dir=run_dir,
        config=config,
        as_of_date=date(2025, 12, 31),
        warnings=[],
    )

    output_names = resolve_ppt_output_names(date(2025, 12, 31))
    assert called["refresh"] == 0
    assert (run_dir / output_names.master_filename) in output_paths
    assert (run_dir / output_names.distribution_filename) in output_paths


def test_write_outputs_runs_config_registered_generator_without_pipeline_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    config = _build_config(tmp_path, screenshot_inputs={})
    config = config.model_copy(
        update={
            "enable_screenshot_replacement": False,
            "output_generators": (
                *config.output_generators,
                OutputGeneratorConfig(
                    name="config_registered_output",
                    registration="tests.test_pipeline_run_outputs:_ConfigRegisteredOutputGenerator",
                    stage="ppt_post_distribution",
                    enabled=True,
                ),
            ),
        }
    )

    monkeypatch.setattr(run_module, "_refresh_ppt_links", lambda _path: True)

    output_paths, _ppt_result = run_module._write_outputs(
        run_dir=run_dir,
        config=config,
        as_of_date=date(2025, 12, 31),
        warnings=[],
    )

    custom_output = run_dir / "config-registered-output.txt"
    assert custom_output in output_paths
    assert custom_output.read_text(encoding="utf-8") == "ok"
