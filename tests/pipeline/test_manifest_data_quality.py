from __future__ import annotations

from datetime import date
from pathlib import Path

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


def test_manifest_build_populates_data_quality_from_warnings(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-13"
    run_dir.mkdir(parents=True)
    artifact = run_dir / "output.csv"
    artifact.write_text("ok\n", encoding="utf-8")

    builder = ManifestBuilder(
        config=_make_config(tmp_path),
        as_of_date=date(2026, 2, 13),
        run_date=date(2026, 2, 14),
    )
    manifest = builder.build(
        run_dir=run_dir,
        input_hashes={"monthly_pptx": "abc123"},
        output_paths=[Path(artifact.name)],
        top_exposures={"all_programs": []},
        top_changes_per_variant={"all_programs": []},
        warnings=[
            "PPT links not refreshed; COM refresh skipped",
            "Reconciliation strict mode failed due to missing/unmapped series",
            {"message": "Notional field missing", "code": "MISSING_NOTIONAL", "row_idx": 3},
        ],
    )

    data_quality = manifest["data_quality"]
    assert data_quality["overall_status"] == "fail"
    assert data_quality["severity_levels"] == ["info", "warn", "fail"]
    assert data_quality["counts"]["total_findings"] == 3
    assert data_quality["counts"]["by_severity"]["fail"] >= 1
    assert data_quality["counts"]["by_category"]["ppt"]["warn"] >= 1
    assert any(
        action["category"] == "reconciliation" and action["severity"] == "fail"
        for action in data_quality["recommended_actions"]
    )


def test_manifest_build_data_quality_defaults_to_info_when_no_warnings(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-13"
    run_dir.mkdir(parents=True)
    artifact = run_dir / "output.csv"
    artifact.write_text("ok\n", encoding="utf-8")

    builder = ManifestBuilder(
        config=_make_config(tmp_path),
        as_of_date=date(2026, 2, 13),
        run_date=date(2026, 2, 14),
    )
    manifest = builder.build(
        run_dir=run_dir,
        input_hashes={"monthly_pptx": "abc123"},
        output_paths=[Path(artifact.name)],
        top_exposures={"all_programs": []},
        top_changes_per_variant={"all_programs": []},
        warnings=[],
    )

    data_quality = manifest["data_quality"]
    assert data_quality["overall_status"] == "info"
    assert data_quality["counts"]["by_severity"] == {"info": 1, "warn": 0, "fail": 0}
    assert data_quality["findings"][0]["code"] == "NO_FINDINGS"
    assert data_quality["recommended_actions"][0]["severity"] == "info"
