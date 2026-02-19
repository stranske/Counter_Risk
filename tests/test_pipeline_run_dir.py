"""Run-directory layout regression tests for pipeline entrypoint."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from counter_risk.pipeline.run import run_pipeline


def _write_placeholder(path: Path, *, content: bytes = b"fixture") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _write_config(
    *, path: Path, output_root: Path, inputs: dict[str, Path], run_date: str | None = None
) -> None:
    lines = [
        "as_of_date: 2026-02-13",
        f"mosers_all_programs_xlsx: {inputs['all_programs']}",
        f"mosers_ex_trend_xlsx: {inputs['ex_trend']}",
        f"mosers_trend_xlsx: {inputs['trend']}",
        f"hist_all_programs_3yr_xlsx: {inputs['hist_all']}",
        f"hist_ex_llc_3yr_xlsx: {inputs['hist_ex']}",
        f"hist_llc_3yr_xlsx: {inputs['hist_llc']}",
        f"monthly_pptx: {inputs['monthly_pptx']}",
        f"output_root: {output_root}",
    ]
    if run_date is not None:
        lines.insert(1, f"run_date: {run_date}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_pipeline_writes_outputs_only_to_repo_root_runs_date_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    requested_output_root = tmp_path / "different-output-root"
    config_path = tmp_path / "config.yml"
    _write_config(path=config_path, output_root=requested_output_root, inputs=inputs)

    monkeypatch.setattr("counter_risk.pipeline.run._resolve_repo_root", lambda: tmp_path)
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

    def _fake_write_outputs(*, run_dir: Path, config: Any, warnings: list[str]) -> list[Path]:
        _ = (config, warnings)
        workbook = run_dir / "current-month.xlsx"
        pptx = run_dir / "current-month.pptx"
        workbook.write_bytes(b"monthly-workbook")
        pptx.write_bytes(b"monthly-pptx")
        return [workbook, pptx]

    monkeypatch.setattr(
        "counter_risk.pipeline.run._update_historical_outputs",
        _fake_historical_update,
    )
    monkeypatch.setattr("counter_risk.pipeline.run._write_outputs", _fake_write_outputs)

    run_dir = run_pipeline(config_path)

    expected_run_dir = tmp_path / "runs" / "2026-02-13"
    assert run_dir == expected_run_dir
    assert run_dir.exists()
    assert not (requested_output_root / "2026-02-13").exists()

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    produced_paths = {run_dir / relative_path for relative_path in manifest["output_paths"]}
    assert produced_paths == {
        run_dir / "historical-output.xlsx",
        run_dir / "current-month.xlsx",
        run_dir / "current-month.pptx",
    }
    for output_path in produced_paths:
        assert output_path.exists()
        assert output_path.is_relative_to(expected_run_dir)


def test_run_directory_creation_same_date_repeat_run_uses_unique_directory_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    _write_config(path=config_path, output_root=tmp_path / "unused-output-root", inputs=inputs)

    monkeypatch.setattr("counter_risk.pipeline.run._resolve_repo_root", lambda: tmp_path)
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

    def _fake_write_outputs(*, run_dir: Path, config: Any, warnings: list[str]) -> list[Path]:
        _ = (config, warnings)
        output = run_dir / "current-month.xlsx"
        output.write_bytes(b"monthly-workbook")
        return [output]

    monkeypatch.setattr(
        "counter_risk.pipeline.run._update_historical_outputs",
        _fake_historical_update,
    )
    monkeypatch.setattr("counter_risk.pipeline.run._write_outputs", _fake_write_outputs)

    first_run_dir = run_pipeline(config_path)
    assert first_run_dir == tmp_path / "runs" / "2026-02-13"

    second_run_dir = run_pipeline(config_path)
    assert second_run_dir == tmp_path / "runs" / "2026-02-13_1"
    assert first_run_dir.exists()
    assert second_run_dir.exists()
    assert (first_run_dir / "historical-output.xlsx").exists()
    assert (second_run_dir / "historical-output.xlsx").exists()


def test_pipeline_run_directory_includes_run_date_when_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    _write_config(
        path=config_path,
        output_root=tmp_path / "unused-output-root",
        inputs=inputs,
        run_date="2026-02-14",
    )

    monkeypatch.setattr("counter_risk.pipeline.run._resolve_repo_root", lambda: tmp_path)
    monkeypatch.setattr("counter_risk.pipeline.run._parse_inputs", lambda _: {})
    monkeypatch.setattr("counter_risk.pipeline.run._validate_parsed_inputs", lambda _: None)
    monkeypatch.setattr("counter_risk.pipeline.run._compute_metrics", lambda _: ({}, {}))
    monkeypatch.setattr(
        "counter_risk.pipeline.run._update_historical_outputs",
        lambda *, run_dir, config, parsed_by_variant, as_of_date, warnings: [],
    )
    monkeypatch.setattr(
        "counter_risk.pipeline.run._write_outputs",
        lambda *, run_dir, config, warnings: [],
    )

    run_dir = run_pipeline(config_path)

    assert run_dir == tmp_path / "runs" / "2026-02-13__run_2026-02-14"
