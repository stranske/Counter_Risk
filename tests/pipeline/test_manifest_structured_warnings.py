"""Tests that structured warning fields survive into the written manifest.

Issue #650: the manifest's top-level ``warnings`` array flattens every collector
record to a single human string, losing the machine-readable ``code``, ``row_idx``,
and source extras. ``warnings_structured`` preserves those discrete fields while the
legacy ``warnings`` string array stays unchanged for backward compatibility.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from counter_risk.config import WorkflowConfig
from counter_risk.pipeline.manifest import ManifestBuilder
from counter_risk.pipeline.warnings import WarningsCollector


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


def _build_builder(tmp_path: Path) -> ManifestBuilder:
    return ManifestBuilder(
        config=_make_config(tmp_path),
        as_of_date=date(2026, 2, 13),
        run_date=date(2026, 2, 14),
    )


def _prepare_run_dir(tmp_path: Path) -> tuple[Path, Path]:
    run_dir = tmp_path / "runs" / "2026-02-13"
    run_dir.mkdir(parents=True)
    artifact = run_dir / "output.csv"
    artifact.write_text("ok\n", encoding="utf-8")
    return run_dir, artifact


def test_collector_structured_fields_survive_into_written_manifest(tmp_path: Path) -> None:
    run_dir, artifact = _prepare_run_dir(tmp_path)
    builder = _build_builder(tmp_path)

    collector = WarningsCollector()
    collector.warn(
        "invalid row",
        code="MISSING_DESCRIPTION",
        row_idx="12",
        description="TY Mar25",
    )

    manifest = builder.build(
        run_dir=run_dir,
        input_hashes={"monthly_pptx": "abc123"},
        output_paths=[Path(artifact.name)],
        top_exposures={"all_programs": []},
        top_changes_per_variant={"all_programs": []},
        warnings=collector.warnings,
    )
    builder.write(run_dir=run_dir, manifest=manifest)

    reloaded = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    structured = reloaded["warnings_structured"]
    assert len(structured) == 1
    entry = structured[0]
    # Discrete fields, not substring-embedded in a single string.
    assert entry["code"] == "MISSING_DESCRIPTION"
    assert entry["row_idx"] == 12
    assert entry["description"] == "TY Mar25"
    assert entry["message"] == "invalid row"


def test_legacy_warnings_string_array_is_unchanged(tmp_path: Path) -> None:
    run_dir, artifact = _prepare_run_dir(tmp_path)
    builder = _build_builder(tmp_path)

    collector = WarningsCollector()
    collector.warn(
        "invalid row",
        code="MISSING_DESCRIPTION",
        row_idx="12",
        description="TY Mar25",
    )

    manifest = builder.build(
        run_dir=run_dir,
        input_hashes={"monthly_pptx": "abc123"},
        output_paths=[Path(artifact.name)],
        top_exposures={"all_programs": []},
        top_changes_per_variant={"all_programs": []},
        warnings=collector.warnings,
    )
    # write() builds the DATA_QUALITY_SUMMARY and runs schema validation; it must not raise.
    builder.write(run_dir=run_dir, manifest=manifest)

    reloaded = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    assert isinstance(reloaded["warnings"], list)
    assert len(reloaded["warnings"]) == 1
    rendered = reloaded["warnings"][0]
    assert rendered.startswith("invalid row (")
    assert "code=MISSING_DESCRIPTION" in rendered
    assert "row_idx=12" in rendered
    assert (run_dir / "DATA_QUALITY_SUMMARY.txt").exists()


def test_plain_string_warnings_round_trip_as_message_only_objects(tmp_path: Path) -> None:
    run_dir, artifact = _prepare_run_dir(tmp_path)
    builder = _build_builder(tmp_path)

    manifest = builder.build(
        run_dir=run_dir,
        input_hashes={"monthly_pptx": "abc123"},
        output_paths=[Path(artifact.name)],
        top_exposures={"all_programs": []},
        top_changes_per_variant={"all_programs": []},
        warnings=[
            "PPT links not refreshed; COM refresh skipped",
            {"message": "Notional field missing", "code": "MISSING_NOTIONAL", "row_idx": 3},
        ],
    )
    builder.write(run_dir=run_dir, manifest=manifest)

    reloaded = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    structured = reloaded["warnings_structured"]

    assert structured[0] == {"message": "PPT links not refreshed; COM refresh skipped"}
    assert structured[1]["code"] == "MISSING_NOTIONAL"
    assert structured[1]["row_idx"] == 3
    assert structured[1]["message"] == "Notional field missing"


def test_empty_warnings_produce_empty_structured_array(tmp_path: Path) -> None:
    run_dir, artifact = _prepare_run_dir(tmp_path)
    builder = _build_builder(tmp_path)

    manifest = builder.build(
        run_dir=run_dir,
        input_hashes={"monthly_pptx": "abc123"},
        output_paths=[Path(artifact.name)],
        top_exposures={"all_programs": []},
        top_changes_per_variant={"all_programs": []},
        warnings=[],
    )
    builder.write(run_dir=run_dir, manifest=manifest)

    reloaded = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert reloaded["warnings_structured"] == []
    assert reloaded["warnings"] == []
