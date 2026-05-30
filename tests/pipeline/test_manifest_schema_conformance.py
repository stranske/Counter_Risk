"""End-to-end conformance of a built manifest against ``manifest_schema()``.

Unlike ``tests/pipeline/test_manifest_schema.py`` (which only asserts on the
schema dict's own shape), this module constructs a real manifest through
``ManifestBuilder.build`` and validates it with ``validate_manifest`` so the run
contract cannot silently drift. It is deliberately *not* named
``test_run_pipeline_*`` and not placed under ``tests/integration`` so it runs in
the PR gate (``pytest -m "not release and not slow"``) rather than only on main.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from counter_risk.config import WorkflowConfig
from counter_risk.pipeline.manifest import ManifestBuilder
from counter_risk.pipeline.manifest_schema import validate_manifest


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


def _build_manifest(tmp_path: Path) -> tuple[ManifestBuilder, Path, dict]:
    run_dir = tmp_path / "runs" / "2026-02-13"
    run_dir.mkdir(parents=True)
    workbook_path = run_dir / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx"
    ppt_path = run_dir / "Monthly Counterparty Exposure Report.pptx"
    workbook_path.write_bytes(b"hist")
    ppt_path.write_bytes(b"ppt")

    builder = ManifestBuilder(
        config=_make_config(tmp_path),
        as_of_date=date(2026, 2, 13),
        run_date=date(2026, 2, 14),
    )
    manifest = builder.build(
        run_dir=run_dir,
        input_hashes={"monthly_pptx": "abc123"},
        output_paths=[Path(workbook_path.name), Path(ppt_path.name)],
        top_exposures={"all_programs": []},
        top_changes_per_variant={"all_programs": []},
        warnings=[],
    )
    return builder, run_dir, manifest


def test_built_manifest_conforms_to_schema(tmp_path: Path) -> None:
    """A manifest produced by ``ManifestBuilder.build`` must satisfy the schema.

    On the un-reconciled schema this FAILS because the unconditionally emitted
    ``date_resolution`` key trips ``additionalProperties: False``; it PASSES once
    the schema accepts the keys the builder already emits.
    """

    _builder, _run_dir, manifest = _build_manifest(tmp_path)

    # Guard against the regression this issue fixes: these keys are emitted by
    # the builder and must be representable in the schema.
    assert "date_resolution" in manifest

    is_valid, reason = validate_manifest(manifest)
    assert is_valid, reason
    assert reason is None


def test_validate_manifest_rejects_unknown_top_level_key(tmp_path: Path) -> None:
    """An un-schema'd top-level key is rejected with a reason naming the key."""

    _builder, _run_dir, manifest = _build_manifest(tmp_path)
    manifest["__unknown__"] = 1

    is_valid, reason = validate_manifest(manifest)
    assert is_valid is False
    assert reason is not None
    assert "__unknown__" in reason


def test_write_raises_on_unknown_key(tmp_path: Path) -> None:
    """``ManifestBuilder.write`` must raise ``ValueError`` for an un-schema'd key.

    This proves a real run that produces an unexpected key fails at write time
    rather than silently persisting a drifted contract.
    """

    builder, run_dir, manifest = _build_manifest(tmp_path)
    manifest["__unknown__"] = 1

    with pytest.raises(ValueError, match="Manifest failed schema validation"):
        builder.write(run_dir=run_dir, manifest=manifest)


def test_validate_manifest_enforces_additional_properties_subschema(tmp_path: Path) -> None:
    """Values under an ``additionalProperties`` schema-object map are validated.

    ``unmatched_mappings.by_variant`` declares
    ``additionalProperties: {"type": "array", ...}``; a non-array value must be
    rejected. Previously only the ``additionalProperties: False`` form was
    enforced, so schema-object maps (``by_variant`` / ``by_category``) silently
    accepted any value, defeating the point of gating the full manifest.
    """

    _builder, _run_dir, manifest = _build_manifest(tmp_path)
    manifest["unmatched_mappings"]["by_variant"]["all_programs"] = "not-an-array"

    is_valid, reason = validate_manifest(manifest)
    assert is_valid is False
    assert reason is not None
    assert "by_variant.all_programs" in reason
    assert "array" in reason


def test_write_validation_failure_leaves_no_partial_output(tmp_path: Path) -> None:
    """A schema-validation failure in ``write`` must not persist partial files.

    Regression guard: the data-quality summary used to be written to disk before
    the manifest was validated, so a failing manifest left a stray
    ``DATA_QUALITY_SUMMARY.txt`` in the run directory. Validation now happens
    before any write, so the failure path is side-effect free.
    """

    builder, run_dir, manifest = _build_manifest(tmp_path)
    manifest["__unknown__"] = 1

    with pytest.raises(ValueError, match="Manifest failed schema validation"):
        builder.write(run_dir=run_dir, manifest=manifest)

    assert not (run_dir / "DATA_QUALITY_SUMMARY.txt").exists()
    assert not (run_dir / "manifest.json").exists()
