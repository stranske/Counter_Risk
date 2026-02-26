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
