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
