"""Manifest PPT status tests for ``ManifestBuilder.build``."""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
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


def test_build_rejects_unknown_ppt_status(tmp_path, builder_with_both_ppt_artifacts):
    builder, paths = builder_with_both_ppt_artifacts
    with pytest.raises(ValueError, match="Invalid ppt_status 'pending'"):
        _build(builder, tmp_path, paths, "pending")


@pytest.mark.parametrize("failed_name", ["manifest.json", "DATA_QUALITY_SUMMARY.txt"])
def test_write_wraps_filesystem_errors(
    tmp_path, builder_with_both_ppt_artifacts, monkeypatch, failed_name
):
    builder, paths = builder_with_both_ppt_artifacts
    manifest = _build(builder, tmp_path, paths, "success")
    original_write = Path.write_text
    failure = OSError("disk is full")

    def write_text(path, *args, **kwargs):
        if path.name == failed_name:
            raise failure
        return original_write(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", write_text)
    with pytest.raises(RuntimeError, match="Failed to write manifest file:") as caught:
        builder.write(run_dir=tmp_path, manifest=manifest)
    assert caught.value.__cause__ is failure


@pytest.mark.parametrize("output_paths", [None, "artifact.xlsx", ["DATA_QUALITY_SUMMARY.txt"]])
def test_summary_registration_preserves_invalid_or_existing_paths(
    builder_with_both_ppt_artifacts, output_paths
):
    builder, _ = builder_with_both_ppt_artifacts
    manifest = {"output_paths": output_paths}
    builder._register_summary_artifact(manifest)
    assert manifest["output_paths"] == output_paths
    if isinstance(output_paths, list):
        assert output_paths == ["DATA_QUALITY_SUMMARY.txt"]


@pytest.mark.parametrize("data_quality", [None, {}, {"overall_status": "unrecognized"}])
def test_summary_without_findings_uses_safe_defaults(builder_with_both_ppt_artifacts, data_quality):
    builder, _ = builder_with_both_ppt_artifacts
    summary = builder._build_data_quality_summary({"data_quality": data_quality})
    assert "Overall status: INFO (GREEN) - Safe to send." in summary
    assert "- Total findings: 0\n- info: 0\n- warn: 0\n- fail: 0" in summary
    for section in ("Findings by category:", "Detailed findings:", "Recommended actions:"):
        assert f"{section}\n- none\n" in summary


def test_summary_sanitizes_counts_and_ignores_malformed_entries(builder_with_both_ppt_artifacts):
    builder, _ = builder_with_both_ppt_artifacts
    summary = builder._build_data_quality_summary(
        {
            "data_quality": {
                "overall_status": " FAIL ",
                "counts": {
                    "total_findings": "bad",
                    "by_severity": {"info": None, "warn": "bad", "fail": "2"},
                    "by_category": {
                        "ignore": None,
                        "source": {"info": None, "warn": "bad", "fail": "2", "total": "2"},
                    },
                },
                "findings": [None],
                "recommended_actions": [None],
            }
        }
    )
    assert "Overall status: FAIL (RED) - Do not send until failing checks are resolved." in summary
    assert "- Total findings: 0\n- info: 0\n- warn: 0\n- fail: 2" in summary
    assert "- source: total=2 (info=0, warn=0, fail=2)" in summary
    assert "ignore" not in summary


@pytest.mark.parametrize("counts", [None, {"total_findings": 0}])
def test_summary_derives_counts_with_normalized_finding_categories(
    builder_with_both_ppt_artifacts, counts
):
    builder, _ = builder_with_both_ppt_artifacts
    summary = builder._build_data_quality_summary(
        {
            "data_quality": {
                "counts": counts,
                "findings": [
                    {"category": "  ", "severity": "unexpected"},
                    {"category": " INPUT ", "severity": " FAIL "},
                    {"category": "input", "severity": "info"},
                ],
            }
        }
    )
    assert "- Total findings: 3\n- info: 1\n- warn: 1\n- fail: 1" in summary
    assert "- input: total=2 (info=1, warn=0, fail=1)" in summary
    assert "- pipeline: total=1 (info=0, warn=1, fail=0)" in summary


@pytest.mark.parametrize(
    ("warning", "message", "structured"),
    [
        ({"message": " only message "}, "only message", {"message": "only message"}),
        (
            {"message": " ", "code": "WARN", "row_idx": 0},
            "code=WARN, row_idx=0",
            {"message": "code=WARN, row_idx=0", "code": "WARN", "row_idx": 0},
        ),
        ({"message": " ", "code": None}, None, None),
        (42, "42", {"message": "42"}),
    ],
)
def test_warning_normalization_preserves_metadata_without_a_message(
    builder_with_both_ppt_artifacts, warning, message, structured
):
    builder, _ = builder_with_both_ppt_artifacts
    assert builder._normalize_warning(warning) == message
    assert builder._normalize_warning_structured(warning) == structured


def test_artifact_path_cannot_reference_run_directory(tmp_path, builder_with_both_ppt_artifacts):
    builder, _ = builder_with_both_ppt_artifacts
    with pytest.raises(ValueError, match="must reference a file, not run_dir itself"):
        builder._to_relative_artifact_path(run_dir=tmp_path, artifact_path=Path("."))


@pytest.mark.parametrize("stdout", ["", " \n", " abc123\n"])
def test_git_sha_normalizes_empty_and_padded_output(monkeypatch, stdout):
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout)
    )
    assert ManifestBuilder._resolve_git_sha() == (stdout.strip() or None)


def test_summary_artifact_is_registered_once_across_repeated_writes(
    tmp_path, builder_with_both_ppt_artifacts
):
    builder, paths = builder_with_both_ppt_artifacts
    manifest = _build(builder, tmp_path, paths, "success")
    builder.write(run_dir=tmp_path, manifest=manifest)
    builder.write(run_dir=tmp_path, manifest=manifest)
    saved = json.loads((tmp_path / "manifest.json").read_text())
    assert saved["output_paths"].count("DATA_QUALITY_SUMMARY.txt") == 1


def test_source_date_conflicts_retain_report_evidence_after_writing(
    tmp_path, builder_with_both_ppt_artifacts
):
    builder, paths = builder_with_both_ppt_artifacts
    source_dates = {
        "all_programs": {"value": "2026-01-31", "source": "worksheet"},
        "trend": {"value": "2025-12-31", "source": "filename"},
    }
    builder = replace(builder, source_report_dates=source_dates)
    manifest = builder.build(
        run_dir=tmp_path,
        input_hashes={},
        output_paths=paths,
        top_exposures={},
        top_changes_per_variant={},
        warnings=[
            {"code": "SOURCE_REPORT_DATE_CONFLICT", "message": "Source periods disagree"},
            {"code": "MISSING_NOTIONAL", "message": "Review notional", "row_idx": 3},
        ],
    )
    builder.write(run_dir=tmp_path, manifest=manifest)
    saved = json.loads((tmp_path / "manifest.json").read_text())
    assert saved["date_resolution"]["source_report_dates"] == source_dates
    findings = {finding["code"]: finding for finding in saved["data_quality"]["findings"]}
    assert findings["SOURCE_REPORT_DATE_CONFLICT"]["details"] == source_dates
    assert "details" not in findings["MISSING_NOTIONAL"]


def test_explicit_ppt_outputs_override_filename_inference(
    tmp_path, builder_with_both_ppt_artifacts
):
    builder, paths = builder_with_both_ppt_artifacts
    # Both deck files exist, but the caller knows generation failed. Preserve
    # those explicit statuses instead of inferring success from their filenames.
    explicit = {
        role: {
            "role": "maintainer_master" if role == "master" else "distribution",
            "status": "failed",
            "path": path.name,
            "generation_step": f"ppt_{role}",
        }
        for role, path in zip(("master", "distribution"), paths, strict=True)
    }
    manifest = builder.build(
        run_dir=tmp_path,
        input_hashes={},
        output_paths=paths,
        top_exposures={},
        top_changes_per_variant={},
        warnings=[],
        ppt_outputs=explicit,
    )
    builder.write(run_dir=tmp_path, manifest=manifest)
    saved = json.loads((tmp_path / "manifest.json").read_text())
    assert saved["ppt_outputs"] == explicit


def test_disabled_ppt_omits_even_explicit_outputs(tmp_path, builder_with_both_ppt_artifacts):
    builder, paths = builder_with_both_ppt_artifacts
    builder = replace(
        builder, config=builder.config.model_copy(update={"enable_ppt_output": False})
    )
    manifest = builder.build(
        run_dir=tmp_path,
        input_hashes={},
        output_paths=paths,
        top_exposures={},
        top_changes_per_variant={},
        warnings=[],
        ppt_outputs={"master": {"status": "failed"}},
    )
    builder.write(run_dir=tmp_path, manifest=manifest)
    saved = json.loads((tmp_path / "manifest.json").read_text())
    assert "ppt_outputs" not in saved


def test_master_only_output_records_distribution_as_skipped(
    tmp_path, builder_with_both_ppt_artifacts
):
    builder, paths = builder_with_both_ppt_artifacts
    paths[1].unlink()
    manifest = _build(builder, tmp_path, paths[:1], "success")
    builder.write(run_dir=tmp_path, manifest=manifest)
    saved = json.loads((tmp_path / "manifest.json").read_text())
    assert saved["ppt_outputs"]["master"]["status"] == "success"
    assert saved["ppt_outputs"]["distribution"] == {
        "role": "distribution",
        "status": "skipped",
        "path": paths[1].name,
        "generation_step": "ppt_distribution",
        "skipped_reason": "Distribution output disabled for this run.",
    }
    assert paths[1].name not in saved["output_paths"]
