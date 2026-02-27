"""Manifest schema definitions and lightweight validation helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_PPT_OUTPUT_ENTRY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["path"],
    "properties": {
        "path": {"type": "string", "minLength": 1},
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


def manifest_schema() -> dict[str, Any]:
    """Return the run manifest schema used by pipeline validation."""

    return {
        "type": "object",
        "required": [
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
        ],
        "properties": {
            "as_of_date": {"type": "string"},
            "run_date": {"type": "string"},
            "run_dir": {"type": "string"},
            "config_snapshot": {"type": "object"},
            "input_hashes": {"type": "object"},
            "output_paths": {"type": "array", "items": {"type": "string"}},
            "ppt_status": {"type": "string", "enum": ["success", "skipped", "failed"]},
            "top_exposures": {"type": "object"},
            "top_changes_per_variant": {"type": "object"},
            "warnings": {"type": "array", "items": {"type": "string"}},
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
                "required": ["has_breaches", "breach_count", "report_path", "warning_banner"],
                "properties": {
                    "has_breaches": {"type": "boolean"},
                    "breach_count": {"type": "integer", "minimum": 0},
                    "report_path": {"type": ["string", "null"]},
                    "warning_banner": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
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
