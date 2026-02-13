from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from counter_risk.pipeline.run import PptProcessingResult, PptProcessingStatus, run_pipeline


@pytest.fixture(autouse=True)
def patch_repo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("counter_risk.pipeline.run._resolve_repo_root", lambda: tmp_path)


def _write_placeholder(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture")


def _write_config(path: Path, inputs: dict[str, Path]) -> None:
    path.write_text(
        "\n".join(
            [
                "as_of_date: 2026-02-13",
                f"mosers_all_programs_xlsx: {inputs['all_programs']}",
                f"mosers_ex_trend_xlsx: {inputs['ex_trend']}",
                f"mosers_trend_xlsx: {inputs['trend']}",
                f"hist_all_programs_3yr_xlsx: {inputs['hist_all']}",
                f"hist_ex_llc_3yr_xlsx: {inputs['hist_ex']}",
                f"hist_llc_3yr_xlsx: {inputs['hist_llc']}",
                f"monthly_pptx: {inputs['monthly_pptx']}",
                f"output_root: {path.parent / 'ignored-output-root'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _prepare_pipeline_for_status_tests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    inputs = {
        "all_programs": tmp_path / "inputs" / "all_programs.xlsx",
        "ex_trend": tmp_path / "inputs" / "ex_trend.xlsx",
        "trend": tmp_path / "inputs" / "trend.xlsx",
        "hist_all": tmp_path / "inputs" / "hist_all.xlsx",
        "hist_ex": tmp_path / "inputs" / "hist_ex.xlsx",
        "hist_llc": tmp_path / "inputs" / "hist_llc.xlsx",
        "monthly_pptx": tmp_path / "inputs" / "monthly.pptx",
    }
    for path in inputs.values():
        _write_placeholder(path)

    config_path = tmp_path / "config.yml"
    _write_config(config_path, inputs)

    monkeypatch.setattr("counter_risk.pipeline.run._parse_inputs", lambda _: {})
    monkeypatch.setattr("counter_risk.pipeline.run._validate_parsed_inputs", lambda _: None)
    monkeypatch.setattr("counter_risk.pipeline.run._compute_metrics", lambda _: ({}, {}))

    def _fake_historical_update(
        *,
        run_dir: Path,
        config: Any,
        parsed_by_variant: dict[str, dict[str, Any]],
        as_of_date: Any,
        warnings: list[str],
    ) -> list[Path]:
        _ = (config, parsed_by_variant, as_of_date, warnings)
        output = run_dir / "historical-output.xlsx"
        output.write_bytes(b"historical")
        return [output]

    monkeypatch.setattr(
        "counter_risk.pipeline.run._update_historical_outputs",
        _fake_historical_update,
    )

    return config_path


def test_pipeline_records_skipped_ppt_status_for_unsupported_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _prepare_pipeline_for_status_tests(tmp_path=tmp_path, monkeypatch=monkeypatch)
    monkeypatch.setattr(
        "counter_risk.pipeline.run._refresh_ppt_links",
        lambda _path: PptProcessingResult(
            status=PptProcessingStatus.SKIPPED,
            error_detail="unsupported platform",
        ),
    )

    run_dir = run_pipeline(config_path)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["ppt_status"] == "skipped"
    assert "PPT links not refreshed; COM refresh skipped" in manifest["warnings"]


def test_pipeline_records_failed_ppt_status_for_runtime_ppt_processing_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _prepare_pipeline_for_status_tests(tmp_path=tmp_path, monkeypatch=monkeypatch)
    monkeypatch.setattr(
        "counter_risk.pipeline.run._refresh_ppt_links",
        lambda _path: PptProcessingResult(
            status=PptProcessingStatus.FAILED,
            error_detail="replacement runtime error",
        ),
    )

    run_dir = run_pipeline(config_path)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["ppt_status"] == "failed"
    assert any(
        warning.startswith("PPT links refresh failed; replacement runtime error")
        for warning in manifest["warnings"]
    )
