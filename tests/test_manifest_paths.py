from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest

from counter_risk.config import WorkflowConfig
from counter_risk.pipeline.manifest import ManifestBuilder


def _make_config(tmp_path: Path) -> WorkflowConfig:
    return WorkflowConfig(
        as_of_date=date(2026, 2, 13),
        mosers_all_programs_xlsx=tmp_path / "all.xlsx",
        mosers_ex_trend_xlsx=tmp_path / "ex.xlsx",
        mosers_trend_xlsx=tmp_path / "trend.xlsx",
        hist_all_programs_3yr_xlsx=tmp_path / "hist-all.xlsx",
        hist_ex_llc_3yr_xlsx=tmp_path / "hist-ex.xlsx",
        hist_llc_3yr_xlsx=tmp_path / "hist-trend.xlsx",
        monthly_pptx=tmp_path / "monthly.pptx",
        output_root=tmp_path / "output-root",
    )


def test_manifest_paths_are_relative_and_resolve_to_existing_files(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-13"
    run_dir.mkdir(parents=True)
    workbook_path = run_dir / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx"
    ppt_path = run_dir / "Monthly Counterparty Exposure Report.pptx"
    workbook_path.write_bytes(b"hist")
    ppt_path.write_bytes(b"ppt")

    builder = ManifestBuilder(config=_make_config(tmp_path))
    manifest = builder.build(
        run_dir=run_dir,
        input_hashes={"monthly_pptx": "abc123"},
        output_paths=[Path(workbook_path.name), Path(ppt_path.name)],
        top_exposures={"all_programs": []},
        top_changes_per_variant={"all_programs": []},
        warnings=[],
    )
    manifest_path = builder.write(run_dir=run_dir, manifest=manifest)

    parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert parsed["run_dir"] == "."
    assert parsed["ppt_status"] in {"success", "skipped", "failed"}

    for artifact_path in parsed["output_paths"]:
        assert not artifact_path.startswith("/")
        assert not re.match(r"^[A-Za-z]:\\", artifact_path)
        assert ".." not in Path(artifact_path).parts
        assert (run_dir / artifact_path).exists()


def test_manifest_build_rejects_nonexistent_artifact_paths(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-13"
    run_dir.mkdir(parents=True)

    builder = ManifestBuilder(config=_make_config(tmp_path))
    with pytest.raises(ValueError, match="do not exist"):
        builder.build(
            run_dir=run_dir,
            input_hashes={"monthly_pptx": "abc123"},
            output_paths=[Path("missing.xlsx")],
            top_exposures={"all_programs": []},
            top_changes_per_variant={"all_programs": []},
            warnings=[],
        )
