"""Integration-style pipeline output tests."""

from __future__ import annotations

from pathlib import Path
from datetime import date
from zipfile import ZipFile

import counter_risk.pipeline.run as run_module
from counter_risk.config import WorkflowConfig
from counter_risk.pipeline.ppt_naming import resolve_ppt_output_names


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
