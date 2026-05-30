"""Provenance + schema-version contract for built run manifests (issue #649).

``ManifestBuilder.build`` must stamp a top-level ``manifest_schema_version`` and a
populated ``provenance`` block (tool / tool_version / git_sha / python_version /
platform) so a replayed or compared run can be tied to the exact code that
produced it. These tests construct a real manifest through ``ManifestBuilder.build``
and validate it against ``manifest_schema()``; on the pre-issue code they FAIL
(the keys are absent and, once required by the schema, rejected) and PASS once the
builder emits real values and the schema accepts them.
"""

from __future__ import annotations

import platform as platform_module
from datetime import date
from pathlib import Path

import counter_risk
from counter_risk.config import WorkflowConfig
from counter_risk.pipeline.manifest import ManifestBuilder
from counter_risk.pipeline.manifest_schema import (
    MANIFEST_SCHEMA_VERSION,
    manifest_schema,
    validate_manifest,
)


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


def _build_manifest(tmp_path: Path) -> dict:
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
    return builder.build(
        run_dir=run_dir,
        input_hashes={"monthly_pptx": "abc123"},
        output_paths=[Path(workbook_path.name), Path(ppt_path.name)],
        top_exposures={"all_programs": []},
        top_changes_per_variant={"all_programs": []},
        warnings=[],
    )


def test_manifest_carries_schema_version(tmp_path: Path) -> None:
    """The built manifest stamps the contract version string."""

    manifest = _build_manifest(tmp_path)

    assert manifest["manifest_schema_version"] == "counter-risk-manifest/v1"
    # The builder and schema must agree on the same version constant.
    assert MANIFEST_SCHEMA_VERSION == "counter-risk-manifest/v1"


def test_manifest_provenance_is_populated_with_real_values(tmp_path: Path) -> None:
    """``provenance`` carries real tool/runtime values, not placeholders."""

    manifest = _build_manifest(tmp_path)
    provenance = manifest["provenance"]

    assert provenance["tool"] == "counter-risk"
    assert provenance["tool_version"] == counter_risk.__version__
    assert provenance["python_version"] == platform_module.python_version()
    assert provenance["platform"] == platform_module.platform()
    # git_sha is best-effort: a 40-char hex SHA inside a checkout, else None.
    git_sha = provenance["git_sha"]
    assert git_sha is None or (isinstance(git_sha, str) and len(git_sha) == 40)
    # Exactly the five contract keys, no extras.
    assert set(provenance) == {
        "tool",
        "tool_version",
        "git_sha",
        "python_version",
        "platform",
    }


def test_schema_requires_version_and_provenance() -> None:
    """The schema treats both new keys as required, top-level properties."""

    schema = manifest_schema()
    assert "manifest_schema_version" in schema["required"]
    assert "provenance" in schema["required"]
    assert "manifest_schema_version" in schema["properties"]
    assert "provenance" in schema["properties"]


def test_built_manifest_with_provenance_conforms_to_schema(tmp_path: Path) -> None:
    """A manifest emitting the new keys validates cleanly (no drift)."""

    manifest = _build_manifest(tmp_path)

    is_valid, reason = validate_manifest(manifest)
    assert is_valid, reason
    assert reason is None


def test_schema_rejects_manifest_missing_provenance(tmp_path: Path) -> None:
    """Dropping ``provenance`` is rejected with a reason naming the key."""

    manifest = _build_manifest(tmp_path)
    del manifest["provenance"]

    is_valid, reason = validate_manifest(manifest)
    assert is_valid is False
    assert reason is not None
    assert "provenance" in reason


def test_schema_rejects_non_string_git_sha(tmp_path: Path) -> None:
    """``git_sha`` is string-or-null; an integer must be rejected."""

    manifest = _build_manifest(tmp_path)
    manifest["provenance"]["git_sha"] = 12345

    is_valid, reason = validate_manifest(manifest)
    assert is_valid is False
    assert reason is not None
    assert "git_sha" in reason
