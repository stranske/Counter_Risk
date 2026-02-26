from __future__ import annotations

from counter_risk.pipeline.manifest_schema import manifest_schema


def test_manifest_schema_defines_master_and_distribution_ppt_outputs() -> None:
    schema = manifest_schema()

    ppt_outputs = schema["properties"]["ppt_outputs"]
    assert ppt_outputs["required"] == ["master", "distribution"]
    assert "master" in ppt_outputs["properties"]
    assert "distribution" in ppt_outputs["properties"]

    assert ppt_outputs["properties"]["master"]["properties"]["path"]["type"] == "string"
    assert ppt_outputs["properties"]["distribution"]["properties"]["path"]["type"] == "string"


def test_manifest_schema_defines_limit_breach_summary_shape() -> None:
    schema = manifest_schema()

    summary = schema["properties"]["limit_breach_summary"]
    assert summary["required"] == ["has_breaches", "breach_count", "report_path", "warning_banner"]
    assert summary["properties"]["has_breaches"]["type"] == "boolean"
    assert summary["properties"]["breach_count"]["type"] == "integer"
    assert summary["properties"]["report_path"]["type"] == ["string", "null"]
    assert summary["properties"]["warning_banner"]["type"] == ["string", "null"]


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
