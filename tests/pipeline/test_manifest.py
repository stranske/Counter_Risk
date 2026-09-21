"""Manifest PPT status tests for ``ManifestBuilder.build``."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from counter_risk.config import WorkflowConfig
from counter_risk.pipeline.manifest import ManifestBuilder
from counter_risk.pipeline.ppt_naming import resolve_ppt_output_names

AS_OF_DATE = date(2026, 2, 13)


@pytest.fixture
def builder_with_both_ppt_artifacts(tmp_path: Path) -> tuple[ManifestBuilder, list[Path]]:
    """Return a builder plus the Master/Distribution paths, both present on disk."""

    config = WorkflowConfig(
        as_of_date=AS_OF_DATE,
        mosers_all_programs_xlsx=tmp_path / "all.xlsx",
        mosers_ex_trend_xlsx=tmp_path / "ex.xlsx",
        mosers_trend_xlsx=tmp_path / "trend.xlsx",
        hist_all_programs_3yr_xlsx=tmp_path / "hist-all.xlsx",
        hist_ex_llc_3yr_xlsx=tmp_path / "hist-ex.xlsx",
        hist_llc_3yr_xlsx=tmp_path / "hist-trend.xlsx",
        monthly_pptx=tmp_path / "monthly.pptx",
        output_root=tmp_path,
    )
    names = resolve_ppt_output_names(AS_OF_DATE)
    output_paths = [tmp_path / names.master_filename, tmp_path / names.distribution_filename]
    for path in output_paths:
        path.write_bytes(b"deck")

    builder = ManifestBuilder(config=config, as_of_date=AS_OF_DATE, run_date=AS_OF_DATE)
    return builder, output_paths


def _build(
    builder: ManifestBuilder,
    run_dir: Path,
    output_paths: list[Path],
    ppt_status: str,
) -> dict[str, Any]:
    return builder.build(
        run_dir=run_dir,
        input_hashes={},
        output_paths=output_paths,
        top_exposures={},
        top_changes_per_variant={},
        warnings=[],
        ppt_status=ppt_status,
    )


def test_build_ppt_outputs_marks_distribution_failed_when_ppt_status_failed(
    tmp_path: Path,
    builder_with_both_ppt_artifacts: tuple[ManifestBuilder, list[Path]],
) -> None:
    """A failed master generation must not report the distribution deck as a success."""

    builder, output_paths = builder_with_both_ppt_artifacts

    manifest = _build(builder, tmp_path, output_paths, "failed")

    ppt_outputs = manifest["ppt_outputs"]
    assert ppt_outputs["master"]["status"] == "failed"
    assert ppt_outputs["distribution"]["status"] == "failed"
    assert ppt_outputs["distribution"]["role"] == "distribution"


def test_build_ppt_outputs_keeps_distribution_success_when_ppt_status_success(
    tmp_path: Path,
    builder_with_both_ppt_artifacts: tuple[ManifestBuilder, list[Path]],
) -> None:
    """The success path is unchanged: both roles still report success."""

    builder, output_paths = builder_with_both_ppt_artifacts

    manifest = _build(builder, tmp_path, output_paths, "success")

    ppt_outputs = manifest["ppt_outputs"]
    assert ppt_outputs["master"]["status"] == "success"
    assert ppt_outputs["distribution"]["status"] == "success"
