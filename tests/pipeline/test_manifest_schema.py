from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from counter_risk.config import WorkflowConfig
from counter_risk.pipeline.manifest import ManifestBuilder
from counter_risk.pipeline.manifest_schema import _matches_type, manifest_schema, validate_manifest


def test_manifest_schema_defines_master_and_distribution_ppt_outputs() -> None:
    schema = manifest_schema()

    ppt_outputs = schema["properties"]["ppt_outputs"]
    assert ppt_outputs["required"] == ["master", "distribution"]
    assert "master" in ppt_outputs["properties"]
    assert "distribution" in ppt_outputs["properties"]

    assert ppt_outputs["properties"]["master"]["required"] == [
        "role",
        "status",
        "path",
        "generation_step",
    ]
    assert ppt_outputs["properties"]["master"]["properties"]["path"]["type"] == "string"
    assert ppt_outputs["properties"]["master"]["properties"]["status"]["enum"] == [
        "success",
        "skipped",
        "failed",
    ]
    assert ppt_outputs["properties"]["master"]["properties"]["generation_step"]["type"] == "string"
    assert ppt_outputs["properties"]["distribution"]["properties"]["path"]["type"] == "string"


def test_manifest_schema_requires_audit_sections() -> None:
    schema = manifest_schema()

    assert "warnings" in schema["required"]
    assert "unmatched_mappings" in schema["required"]
    assert "missing_inputs" in schema["required"]
    assert "reconciliation_results" in schema["required"]

    assert schema["properties"]["warnings"]["type"] == "array"
    assert schema["properties"]["unmatched_mappings"]["type"] == "object"
    assert schema["properties"]["missing_inputs"]["type"] == "object"
    assert schema["properties"]["reconciliation_results"]["type"] == "object"
    assert schema["properties"]["missing_inputs"]["required"] == [
        "required",
        "missing_required",
        "optional_missing",
        "is_complete",
    ]


def test_manifest_schema_defines_limit_breach_summary_shape() -> None:
    schema = manifest_schema()

    summary = schema["properties"]["limit_breach_summary"]
    assert summary["required"] == [
        "has_breaches",
        "breach_count",
        "max_severity",
        "warning_breach_count",
        "fail_breach_count",
        "report_path",
        "warning_banner",
    ]
    assert summary["properties"]["has_breaches"]["type"] == "boolean"
    assert summary["properties"]["breach_count"]["type"] == "integer"
    assert summary["properties"]["max_severity"]["type"] == ["string", "null"]
    assert summary["properties"]["warning_breach_count"]["type"] == "integer"
    assert summary["properties"]["fail_breach_count"]["type"] == "integer"
    assert summary["properties"]["report_path"]["type"] == ["string", "null"]
    assert summary["properties"]["warning_banner"]["type"] == ["string", "null"]


def test_manifest_schema_defines_repo_cash_summary_shape() -> None:
    schema = manifest_schema()

    summary = schema["properties"]["repo_cash_summary"]
    assert "repo_cash_summary" not in schema["required"]
    assert summary["required"] == [
        "source_type",
        "source_path",
        "skipped_reason",
        "overrides_path",
        "applied_override_count",
        "raw_override_row_count",
        "override_audit_rows",
        "duplicate_counterparty_names",
        "orphan_override_counterparties",
        "counterparty_count",
        "total_cash",
        "required_counterparties",
        "missing_required_counterparties",
        "reconciliation_findings",
        "fail_policy",
    ]
    assert summary["properties"]["source_path"]["type"] == ["string", "null"]
    assert summary["properties"]["applied_override_count"]["type"] == "integer"
    assert summary["properties"]["raw_override_row_count"]["type"] == "integer"
    assert summary["properties"]["override_audit_rows"]["items"]["required"] == [
        "counterparty",
        "raw_counterparty",
        "cash_value",
        "note",
    ]
    assert summary["properties"]["reconciliation_findings"]["items"]["required"] == [
        "code",
        "severity",
        "message",
    ]


def test_manifest_schema_defines_data_quality_shape() -> None:
    schema = manifest_schema()

    data_quality = schema["properties"]["data_quality"]
    assert data_quality["required"] == [
        "overall_status",
        "severity_levels",
        "findings",
        "counts",
        "recommended_actions",
    ]
    assert data_quality["properties"]["overall_status"]["enum"] == ["info", "warn", "fail"]
    assert data_quality["properties"]["findings"]["items"]["required"] == [
        "category",
        "severity",
        "code",
        "message",
    ]
    assert data_quality["properties"]["findings"]["items"]["properties"]["severity"]["enum"] == [
        "info",
        "warn",
        "fail",
    ]
    assert data_quality["properties"]["recommended_actions"]["items"]["required"] == [
        "category",
        "severity",
        "action",
    ]


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), float("-inf"), True, False, "1", None]
)
def test_number_type_rejects_non_finite_and_non_numeric_values(value: object) -> None:
    assert _matches_type(value, "number") is False


@pytest.mark.parametrize("value", [0, -1, 10**400, 0.0, -1.5, 1.7976931348623157e308])
def test_number_type_preserves_finite_floats_and_arbitrary_size_integers(
    value: int | float,
) -> None:
    assert _matches_type(value, "number") is True


@pytest.fixture
def numeric_manifest(tmp_path: Path) -> tuple[ManifestBuilder, dict[str, Any]]:
    config = WorkflowConfig(
        as_of_date=date(2026, 2, 13),
        mosers_all_programs_xlsx=tmp_path / "all.xlsx",
        mosers_ex_trend_xlsx=tmp_path / "ex.xlsx",
        mosers_trend_xlsx=tmp_path / "trend.xlsx",
        hist_all_programs_3yr_xlsx=tmp_path / "hist-all.xlsx",
        hist_ex_llc_3yr_xlsx=tmp_path / "hist-ex.xlsx",
        hist_llc_3yr_xlsx=tmp_path / "hist-trend.xlsx",
        monthly_pptx=tmp_path / "monthly.pptx",
        output_root=tmp_path,
    )
    builder = ManifestBuilder(
        config=config, as_of_date=config.as_of_date, run_date=config.as_of_date
    )
    manifest = builder.build(
        run_dir=tmp_path,
        input_hashes={},
        output_paths=[],
        top_exposures={
            "all_programs": [
                {
                    "counterparty": "Example",
                    "notional": 1.0,
                    "evidence": {
                        "source_id": "example",
                        "sheet": None,
                        "row": None,
                        "method": "test",
                        "confidence": None,
                    },
                }
            ]
        },
        top_changes_per_variant={},
        warnings=[],
        concentration_metrics=[{"hhi": 0.25}],
    )
    assert validate_manifest(manifest) == (True, None)
    return builder, manifest


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("field", ["notional", "confidence", "hhi"])
def test_manifest_rejects_non_finite_numbers_before_writing(
    numeric_manifest: tuple[ManifestBuilder, dict[str, Any]],
    tmp_path: Path,
    field: str,
    value: float,
) -> None:
    builder, manifest = numeric_manifest
    exposure = manifest["top_exposures"]["all_programs"][0]
    if field == "confidence":
        exposure["evidence"][field] = value
        path = "top_exposures.all_programs[0].evidence.confidence"
    elif field == "notional":
        exposure[field] = value
        path = "top_exposures.all_programs[0].notional"
    else:
        manifest["concentration_metrics"][0][field] = value
        path = "concentration_metrics[0].hhi"

    valid, reason = validate_manifest(manifest)
    assert valid is False
    assert reason is not None and path in reason and "type number" in reason
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="Manifest failed schema validation"):
        builder.write(run_dir=tmp_path, manifest=manifest)
    after = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert after == before
    assert not (tmp_path / "manifest.json").exists()


@pytest.mark.parametrize("value", [0, -1, 10**400, 0.0, -1.5, 1.7976931348623157e308])
def test_finite_manifest_numbers_remain_json_serializable(
    numeric_manifest: tuple[ManifestBuilder, dict[str, Any]], tmp_path: Path, value: int | float
) -> None:
    builder, manifest = numeric_manifest
    manifest["top_exposures"]["all_programs"][0]["notional"] = value
    assert validate_manifest(manifest) == (True, None)
    json.dumps(manifest, allow_nan=False)
    builder.write(run_dir=tmp_path, manifest=manifest)
    saved = json.loads((tmp_path / "manifest.json").read_text())
    assert saved["top_exposures"]["all_programs"][0]["notional"] == value


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("container", ["mapping", "list", "tuple"])
def test_manifest_rejects_nonfinite_in_unconstrained_fields_before_writing(
    numeric_manifest: tuple[ManifestBuilder, dict[str, Any]],
    tmp_path: Path,
    container: str,
    value: float,
) -> None:
    builder, manifest = numeric_manifest
    nested: Any = {"delta": value}
    if container == "list":
        nested = [nested]
    elif container == "tuple":
        nested = (nested,)
    manifest["top_changes_per_variant"]["all_programs"] = nested
    # Protect existing output too: a failed write must neither create nor overwrite files.
    (tmp_path / "manifest.json").write_text("existing manifest", encoding="utf-8")
    (tmp_path / "DATA_QUALITY_SUMMARY.txt").write_text("existing summary", encoding="utf-8")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    valid, reason = validate_manifest(manifest)
    assert valid is False
    assert reason is not None and "top_changes_per_variant.all_programs" in reason
    assert "delta" in reason and "finite" in reason
    with pytest.raises(ValueError, match="Manifest failed schema validation"):
        builder.write(run_dir=tmp_path, manifest=manifest)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before


def test_manifest_preserves_valid_unconstrained_values(
    numeric_manifest: tuple[ManifestBuilder, dict[str, Any]], tmp_path: Path
) -> None:
    builder, manifest = numeric_manifest
    values = [None, True, False, "NaN", 10**400, 0.0, -1.5]
    manifest["top_changes_per_variant"]["all_programs"] = {"values": values}
    assert validate_manifest(manifest) == (True, None)
    builder.write(run_dir=tmp_path, manifest=manifest)
    saved = json.loads((tmp_path / "manifest.json").read_text())
    assert saved["top_changes_per_variant"]["all_programs"]["values"] == values
