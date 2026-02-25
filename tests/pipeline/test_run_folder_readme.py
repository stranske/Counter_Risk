from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

import counter_risk.pipeline.run as run_module
from counter_risk.config import WorkflowConfig
from counter_risk.pipeline.manifest import ManifestBuilder
from counter_risk.pipeline.ppt_naming import PptOutputNames
from counter_risk.pipeline.ppt_naming import resolve_ppt_output_names
from counter_risk.pipeline.run_folder_outputs import (
    RunFolderReadmePptOutputs,
    build_run_folder_readme_content,
)


def test_readme_content_includes_filenames_and_three_numbered_steps_in_order() -> None:
    output_names = resolve_ppt_output_names(date(2026, 1, 31))
    content = build_run_folder_readme_content(
        date(2026, 1, 31),
        RunFolderReadmePptOutputs(
            master=Path(output_names.master_filename),
            distribution=Path(output_names.distribution_filename),
        ),
    )

    assert output_names.master_filename in content
    assert output_names.distribution_filename in content

    step_1 = re.search(r"^1\.", content, flags=re.MULTILINE)
    step_2 = re.search(r"^2\.", content, flags=re.MULTILINE)
    step_3 = re.search(r"^3\.", content, flags=re.MULTILINE)

    assert step_1 is not None
    assert step_2 is not None
    assert step_3 is not None
    assert step_1.start() < step_2.start() < step_3.start()


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


def test_run_folder_readme_created_when_ppt_enabled_and_registered_in_manifest(
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

    output_paths, _ = run_module._write_outputs(
        run_dir=run_dir,
        config=config,
        as_of_date=date(2026, 1, 31),
        warnings=[],
    )

    readme_path = run_dir / "README.txt"
    assert readme_path.exists()
    content = readme_path.read_text(encoding="utf-8")
    output_names = resolve_ppt_output_names(date(2026, 1, 31))
    assert output_names.master_filename in content
    assert output_names.distribution_filename in content
    assert "\n1." in content
    assert "\n2." in content
    assert "\n3." in content

    manifest = ManifestBuilder(
        config=config,
        as_of_date=date(2026, 1, 31),
        run_date=date(2026, 2, 1),
    ).build(
        run_dir=run_dir,
        input_hashes={},
        output_paths=output_paths,
        top_exposures={},
        top_changes_per_variant={},
        warnings=[],
        ppt_status=run_module.PptProcessingStatus.SUCCESS.value,
    )
    readme_manifest_paths = [
        path for path in manifest["output_paths"] if path.endswith("README.txt")
    ]
    assert readme_manifest_paths == ["README.txt"]


def test_run_folder_readme_content_uses_custom_resolved_output_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    config = _build_config(tmp_path, enable_ppt_output=True)
    resolved_names = PptOutputNames(
        master_filename="Custom Master Deck - 2026-01-31.pptx",
        distribution_filename="Custom Distribution Deck - 2026-01-31.pptx",
    )

    monkeypatch.setattr(run_module, "resolve_ppt_output_names", lambda _as_of_date: resolved_names)
    monkeypatch.setattr(
        run_module,
        "_refresh_ppt_links",
        lambda _path: run_module.PptProcessingResult(status=run_module.PptProcessingStatus.SUCCESS),
    )

    output_paths, _ = run_module._write_outputs(
        run_dir=run_dir,
        config=config,
        as_of_date=date(2026, 1, 31),
        warnings=[],
    )

    readme_path = run_dir / "README.txt"
    content = readme_path.read_text(encoding="utf-8")
    assert resolved_names.master_filename in content
    assert resolved_names.distribution_filename in content
    assert (run_dir / resolved_names.master_filename) in output_paths
    assert (run_dir / resolved_names.distribution_filename) in output_paths


def test_run_folder_readme_not_created_when_ppt_disabled(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    config = _build_config(tmp_path, enable_ppt_output=False)

    run_module._write_outputs(
        run_dir=run_dir,
        config=config,
        as_of_date=date(2026, 1, 31),
        warnings=[],
    )

    assert not (run_dir / "README.txt").exists()


@pytest.mark.parametrize(
    ("status", "expect_readme"),
    [
        (run_module.PptProcessingStatus.SUCCESS, True),
        (run_module.PptProcessingStatus.FAILED, False),
    ],
)
def test_run_folder_readme_creation_differs_for_master_success_and_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: run_module.PptProcessingStatus,
    expect_readme: bool,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    config = _build_config(tmp_path, enable_ppt_output=True)

    def _refresh(_path: Path) -> run_module.PptProcessingResult:
        return run_module.PptProcessingResult(status=status, error_detail="refresh failed")

    monkeypatch.setattr(run_module, "_refresh_ppt_links", _refresh)

    run_module._write_outputs(
        run_dir=run_dir,
        config=config,
        as_of_date=date(2026, 1, 31),
        warnings=[],
    )

    assert (run_dir / "README.txt").exists() is expect_readme
