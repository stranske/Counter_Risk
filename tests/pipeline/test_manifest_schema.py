from __future__ import annotations

from counter_risk.pipeline.manifest_schema import manifest_schema


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
    assert summary["required"] == ["has_breaches", "breach_count", "report_path", "warning_banner"]
    assert summary["properties"]["has_breaches"]["type"] == "boolean"
    assert summary["properties"]["breach_count"]["type"] == "integer"
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
