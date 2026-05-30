"""Manifest schema definitions and lightweight validation helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Contract version stamped onto every manifest via ``ManifestBuilder.build``.
# Bump this (and the schema below) when the manifest contract changes in a way
# consumers must branch on. Kept beside the schema so the version and the shape
# it describes evolve together.
MANIFEST_SCHEMA_VERSION = "counter-risk-manifest/v1"

_PPT_OUTPUT_ENTRY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["role", "status", "path", "generation_step"],
    "properties": {
        "role": {"type": "string", "enum": ["maintainer_master", "distribution"]},
        "status": {"type": "string", "enum": ["success", "skipped", "failed"]},
        "path": {"type": "string", "minLength": 1},
        "generation_step": {"type": "string", "minLength": 1},
        "skipped_reason": {"type": "string", "minLength": 1},
    },
    "additionalProperties": False,
}

_DATA_QUALITY_SEVERITY_SCHEMA: dict[str, Any] = {"type": "string", "enum": ["info", "warn", "fail"]}

_DATA_QUALITY_FINDING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["category", "severity", "code", "message"],
    "properties": {
        "category": {"type": "string", "minLength": 1},
        "severity": _DATA_QUALITY_SEVERITY_SCHEMA,
        "code": {"type": "string", "minLength": 1},
        "message": {"type": "string"},
    },
    "additionalProperties": False,
}

_DATA_QUALITY_ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["category", "severity", "action"],
    "properties": {
        "category": {"type": "string", "minLength": 1},
        "severity": _DATA_QUALITY_SEVERITY_SCHEMA,
        "action": {"type": "string", "minLength": 1},
    },
    "additionalProperties": False,
}

_DATA_QUALITY_COUNTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["total_findings", "by_severity", "by_category"],
    "properties": {
        "total_findings": {"type": "integer", "minimum": 0},
        "by_severity": {
            "type": "object",
            "required": ["info", "warn", "fail"],
            "properties": {
                "info": {"type": "integer", "minimum": 0},
                "warn": {"type": "integer", "minimum": 0},
                "fail": {"type": "integer", "minimum": 0},
            },
            "additionalProperties": False,
        },
        "by_category": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "required": ["info", "warn", "fail", "total"],
                "properties": {
                    "info": {"type": "integer", "minimum": 0},
                    "warn": {"type": "integer", "minimum": 0},
                    "fail": {"type": "integer", "minimum": 0},
                    "total": {"type": "integer", "minimum": 0},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

_DATA_QUALITY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["overall_status", "severity_levels", "findings", "counts", "recommended_actions"],
    "properties": {
        "overall_status": _DATA_QUALITY_SEVERITY_SCHEMA,
        "severity_levels": {
            "type": "array",
            "items": _DATA_QUALITY_SEVERITY_SCHEMA,
            "minItems": 3,
        },
        "findings": {"type": "array", "items": _DATA_QUALITY_FINDING_SCHEMA},
        "counts": _DATA_QUALITY_COUNTS_SCHEMA,
        "recommended_actions": {"type": "array", "items": _DATA_QUALITY_ACTION_SCHEMA},
    },
    "additionalProperties": False,
}

_REPO_CASH_FINDING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["code", "severity", "message"],
    "properties": {
        "code": {"type": "string", "minLength": 1},
        "severity": _DATA_QUALITY_SEVERITY_SCHEMA,
        "message": {"type": "string"},
    },
    "additionalProperties": False,
}

_REPO_CASH_OVERRIDE_ROW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["counterparty", "raw_counterparty", "cash_value", "note"],
    "properties": {
        "counterparty": {"type": "string", "minLength": 1},
        "raw_counterparty": {"type": "string", "minLength": 1},
        "cash_value": {"type": "string", "minLength": 1},
        "note": {"type": "string"},
    },
    "additionalProperties": False,
}

_REPO_CASH_SUMMARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
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
    ],
    "properties": {
        "source_type": {"type": "string"},
        "source_path": {"type": ["string", "null"]},
        "skipped_reason": {"type": ["string", "null"]},
        "overrides_path": {"type": ["string", "null"]},
        "applied_override_count": {"type": "integer", "minimum": 0},
        "raw_override_row_count": {"type": "integer", "minimum": 0},
        "override_audit_rows": {"type": "array", "items": _REPO_CASH_OVERRIDE_ROW_SCHEMA},
        "duplicate_counterparty_names": {"type": "array", "items": {"type": "string"}},
        "orphan_override_counterparties": {"type": "array", "items": {"type": "string"}},
        "counterparty_count": {"type": "integer", "minimum": 0},
        "total_cash": {"type": "number"},
        "required_counterparties": {"type": "array", "items": {"type": "string"}},
        "missing_required_counterparties": {"type": "array", "items": {"type": "string"}},
        "reconciliation_findings": {"type": "array", "items": _REPO_CASH_FINDING_SCHEMA},
        "fail_policy": {"type": "string"},
        "applied_to_totals": {"type": "boolean"},
    },
    "additionalProperties": False,
}

# A single date-resolution entry as emitted by ``DateResolution.to_manifest_entry``
# (``src/counter_risk/dates.py``) and the unresolved fallback in
# ``ManifestBuilder._render_date_resolution_entry``. ``details`` is an open-ended
# provenance map (e.g. ``{"config_field": "as_of_date"}``), so it stays untyped.
_DATE_RESOLUTION_ENTRY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["value", "source", "details"],
    "properties": {
        "value": {"type": "string"},
        "source": {"type": "string"},
        "details": {"type": "object"},
    },
    "additionalProperties": False,
}

# ``date_resolution`` block emitted unconditionally by ``ManifestBuilder.build``
# (``src/counter_risk/pipeline/manifest.py``).
_DATE_RESOLUTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["as_of_date", "run_date"],
    "properties": {
        "as_of_date": _DATE_RESOLUTION_ENTRY_SCHEMA,
        "run_date": _DATE_RESOLUTION_ENTRY_SCHEMA,
    },
    "additionalProperties": False,
}

# ``risk_proxy_summary`` block emitted conditionally by ``ManifestBuilder.build``
# (sourced from ``_build_risk_proxy_summary`` in ``src/counter_risk/pipeline/run.py``).
# The per-variant payload is open-ended, so the inner objects stay permissive.
_RISK_PROXY_SUMMARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["outputs", "by_variant"],
    "properties": {
        "outputs": {"type": "object"},
        "by_variant": {"type": "object"},
    },
    "additionalProperties": True,
}

# ``provenance`` block emitted unconditionally by ``ManifestBuilder._build_provenance``
# (``src/counter_risk/pipeline/manifest.py``). Ties a run to the exact code that
# produced it. ``git_sha`` is nullable because best-effort resolution must still
# succeed outside a git checkout (installed wheel, archived source).
_PROVENANCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["tool", "tool_version", "git_sha", "python_version", "platform"],
    "properties": {
        "tool": {"type": "string", "minLength": 1},
        "tool_version": {"type": "string", "minLength": 1},
        "git_sha": {"type": ["string", "null"]},
        "python_version": {"type": "string", "minLength": 1},
        "platform": {"type": "string", "minLength": 1},
    },
    "additionalProperties": False,
}

_EVIDENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["source_id", "sheet", "row", "method", "confidence"],
    "properties": {
        "source_id": {"type": "string", "minLength": 1},
        "sheet": {"type": ["string", "null"]},
        "row": {"type": ["integer", "null"], "minimum": 1},
        "method": {"type": "string", "minLength": 1},
        "confidence": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
    },
    "additionalProperties": False,
}

_TOP_EXPOSURE_ENTRY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["counterparty", "notional", "evidence"],
    "properties": {
        "counterparty": {"type": "string"},
        "notional": {"type": "number"},
        "evidence": _EVIDENCE_SCHEMA,
    },
    "additionalProperties": False,
}

_TOP_EXPOSURES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": {
        "type": "array",
        "items": _TOP_EXPOSURE_ENTRY_SCHEMA,
    },
}


def manifest_schema() -> dict[str, Any]:
    """Return the run manifest schema used by pipeline validation."""

    return {
        "type": "object",
        "required": [
            "manifest_schema_version",
            "as_of_date",
            "run_date",
            "run_dir",
            "config_snapshot",
            "input_hashes",
            "output_paths",
            "ppt_status",
            "top_exposures",
            "top_changes_per_variant",
            "warnings",
            "data_quality",
            "unmatched_mappings",
            "missing_inputs",
            "reconciliation_results",
            "provenance",
        ],
        "properties": {
            "manifest_schema_version": {"type": "string", "minLength": 1},
            "provenance": _PROVENANCE_SCHEMA,
            "as_of_date": {"type": "string"},
            "run_date": {"type": "string"},
            "run_dir": {"type": "string"},
            "config_snapshot": {"type": "object"},
            "input_hashes": {"type": "object"},
            "output_paths": {"type": "array", "items": {"type": "string"}},
            "ppt_status": {"type": "string", "enum": ["success", "skipped", "failed"]},
            "top_exposures": _TOP_EXPOSURES_SCHEMA,
            "top_changes_per_variant": {"type": "object"},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "warnings_structured": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["message"],
                    "properties": {
                        "message": {"type": "string"},
                        "code": {"type": "string"},
                        "row_idx": {"type": "integer"},
                    },
                    "additionalProperties": True,
                },
            },
            "data_quality": _DATA_QUALITY_SCHEMA,
            "unmatched_mappings": {
                "type": "object",
                "required": ["count", "by_variant"],
                "properties": {
                    "count": {"type": "integer", "minimum": 0},
                    "by_variant": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                    },
                },
                "additionalProperties": True,
            },
            "missing_inputs": {
                "type": "object",
                "required": ["required", "missing_required", "optional_missing", "is_complete"],
                "properties": {
                    "required": {"type": "array", "items": {"type": "string"}},
                    "missing_required": {"type": "array", "items": {"type": "string"}},
                    "optional_missing": {"type": "array", "items": {"type": "string"}},
                    "is_complete": {"type": "boolean"},
                },
                "additionalProperties": True,
            },
            "reconciliation_results": {
                "type": "object",
                "required": ["status", "fail_policy", "total_gap_count", "by_variant"],
                "properties": {
                    "status": {"type": "string"},
                    "fail_policy": {"type": "string"},
                    "total_gap_count": {"type": "integer", "minimum": 0},
                    "by_variant": {"type": "object"},
                },
                "additionalProperties": True,
            },
            "ppt_outputs": {
                "type": "object",
                "required": ["master", "distribution"],
                "properties": {
                    "master": _PPT_OUTPUT_ENTRY_SCHEMA,
                    "distribution": _PPT_OUTPUT_ENTRY_SCHEMA,
                },
                "additionalProperties": False,
            },
            "concentration_metrics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "variant": {"type": "string"},
                        "segment": {"type": "string"},
                        "top5_share": {"type": "number"},
                        "top10_share": {"type": "number"},
                        "hhi": {"type": "number"},
                    },
                },
            },
            "limit_breach_summary": {
                "type": "object",
                "required": [
                    "has_breaches",
                    "breach_count",
                    "max_severity",
                    "warning_breach_count",
                    "fail_breach_count",
                    "report_path",
                    "warning_banner",
                ],
                "properties": {
                    "has_breaches": {"type": "boolean"},
                    "breach_count": {"type": "integer", "minimum": 0},
                    "max_severity": {"type": ["string", "null"], "enum": ["warning", "fail", None]},
                    "warning_breach_count": {"type": "integer", "minimum": 0},
                    "fail_breach_count": {"type": "integer", "minimum": 0},
                    "report_path": {"type": ["string", "null"]},
                    "warning_banner": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
            "repo_cash_summary": _REPO_CASH_SUMMARY_SCHEMA,
            "date_resolution": _DATE_RESOLUTION_SCHEMA,
            "risk_proxy_summary": _RISK_PROXY_SUMMARY_SCHEMA,
        },
        "additionalProperties": False,
    }


def validate_manifest_ppt_outputs(
    manifest: Mapping[str, Any], *, ppt_enabled: bool
) -> tuple[bool, str | None]:
    """Validate Master/Distribution PPT entries with deterministic failure reasons."""

    ppt_outputs = manifest.get("ppt_outputs")
    if not ppt_enabled:
        if ppt_outputs is None:
            return True, None
        return False, "Manifest must not include ppt_outputs when PPT generation is disabled."

    if not isinstance(ppt_outputs, Mapping):
        return False, "Manifest must include ppt_outputs with Master and Distribution entries."

    has_master = "master" in ppt_outputs
    has_distribution = "distribution" in ppt_outputs
    if has_master and has_distribution:
        return True, None
    if has_master:
        return False, "Manifest ppt_outputs is missing required Distribution PPT entry."
    if has_distribution:
        return False, "Manifest ppt_outputs is missing required Master PPT entry."
    return False, "Manifest ppt_outputs must include both Master and Distribution entries."


def validate_manifest_data_quality(manifest: Mapping[str, Any]) -> tuple[bool, str | None]:
    """Validate data_quality shape for focused acceptance checks."""

    data_quality = manifest.get("data_quality")
    if not isinstance(data_quality, Mapping):
        return False, "Manifest must include data_quality object."

    required_fields = [
        "overall_status",
        "severity_levels",
        "findings",
        "counts",
        "recommended_actions",
    ]
    for field in required_fields:
        if field not in data_quality:
            if field == "recommended_actions":
                return False, "Manifest data_quality is missing required recommended_actions field."
            return False, f"Manifest data_quality is missing required {field} field."

    recommended_actions = data_quality.get("recommended_actions")
    if not isinstance(recommended_actions, list):
        return False, "Manifest data_quality recommended_actions must be an array."

    valid_severities = {"info", "warn", "fail"}
    for index, action in enumerate(recommended_actions):
        if not isinstance(action, Mapping):
            return (
                False,
                f"Manifest data_quality recommended_actions[{index}] must be an object.",
            )

        category = action.get("category")
        if not isinstance(category, str) or not category.strip():
            return (
                False,
                f"Manifest data_quality recommended_actions[{index}] must include non-empty category.",
            )

        severity = action.get("severity")
        if not isinstance(severity, str) or severity not in valid_severities:
            return (
                False,
                "Manifest data_quality recommended_actions"
                f"[{index}].severity must be one of: info, warn, fail.",
            )

        description = action.get("action")
        if not isinstance(description, str) or not description.strip():
            return (
                False,
                f"Manifest data_quality recommended_actions[{index}] must include non-empty action.",
            )

    return True, None


def _matches_type(value: Any, type_name: str) -> bool:
    """Return True when ``value`` matches a single JSON Schema ``type`` name."""

    if type_name == "object":
        return isinstance(value, Mapping)
    if type_name == "array":
        return isinstance(value, list)
    if type_name == "string":
        return isinstance(value, str)
    if type_name == "integer":
        # JSON integers are not booleans, even though ``bool`` subclasses ``int``.
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if type_name == "boolean":
        return isinstance(value, bool)
    if type_name == "null":
        return value is None
    # Unknown type keyword: be permissive rather than reject valid runs.
    return True


def _check_node(value: Any, schema: Mapping[str, Any], path: str) -> str | None:
    """Validate ``value`` against ``schema`` at ``path``.

    Returns a deterministic, human-readable reason on the first failure, or
    ``None`` when the node (and its descendants) conform. Supports the subset of
    JSON Schema the manifest schema actually uses: ``type`` (including union
    types like ``["string", "null"]``), ``required``, ``enum``, ``minimum``,
    ``minLength``, ``minItems``, nested ``properties``, array ``items``, and
    ``additionalProperties`` in all three forms the manifest schema relies on:
    ``False`` (reject unknown keys), ``True`` (accept any), and the schema-object
    form (validate every non-``properties`` key's value against that sub-schema,
    e.g. the ``by_category`` / ``by_variant`` maps).
    """

    expected_type = schema.get("type")
    if expected_type is not None:
        type_names = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_matches_type(value, name) for name in type_names):
            rendered = " or ".join(str(name) for name in type_names)
            return f"{path} must be of type {rendered}, got {type(value).__name__}"

    if "enum" in schema and value not in schema["enum"]:
        allowed = ", ".join(repr(option) for option in schema["enum"])
        return f"{path} must be one of: {allowed}"

    if (
        "minimum" in schema
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value < schema["minimum"]
    ):
        return f"{path} must be >= {schema['minimum']}"

    if "minLength" in schema and isinstance(value, str) and len(value) < schema["minLength"]:
        return f"{path} must have at least {schema['minLength']} character(s)"

    if "minItems" in schema and isinstance(value, list) and len(value) < schema["minItems"]:
        return f"{path} must have at least {schema['minItems']} item(s)"

    if isinstance(value, Mapping):
        for required_key in schema.get("required", []):
            if required_key not in value:
                return f"{path} is missing required key '{required_key}'"

        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, child_value in value.items():
            if key in properties:
                child_path = f"{path}.{key}" if path else str(key)
                reason = _check_node(child_value, properties[key], child_path)
                if reason is not None:
                    return reason
            elif additional is False:
                return f"{path} contains unexpected key '{key}' (additionalProperties is false)"
            elif isinstance(additional, Mapping):
                # Schema-object form: every key not covered by ``properties`` must
                # validate against the ``additionalProperties`` sub-schema (e.g. the
                # ``by_category`` / ``by_variant`` maps in ``manifest_schema()``).
                child_path = f"{path}.{key}" if path else str(key)
                reason = _check_node(child_value, additional, child_path)
                if reason is not None:
                    return reason

    if isinstance(value, list):
        items_schema = schema.get("items")
        if isinstance(items_schema, Mapping):
            for index, item in enumerate(value):
                reason = _check_node(item, items_schema, f"{path}[{index}]")
                if reason is not None:
                    return reason

    return None


def validate_manifest(manifest: Mapping[str, Any]) -> tuple[bool, str | None]:
    """Validate a full run manifest against :func:`manifest_schema`.

    Returns ``(True, None)`` when ``manifest`` conforms, or ``(False, reason)``
    with a deterministic human-readable explanation of the first violation
    (type mismatch, missing required key, bad enum value, an unknown
    top-level/nested key rejected by ``additionalProperties: False``, or a value
    under an ``additionalProperties`` schema-object map that violates that
    sub-schema).
    """

    reason = _check_node(manifest, manifest_schema(), "manifest")
    if reason is not None:
        return False, reason
    return True, None
