"""Targeted manifest data quality validation tests for acceptance selectors."""

from __future__ import annotations

from counter_risk.pipeline.manifest_schema import validate_manifest_data_quality


def test_manifest_data_quality_with_recommended_actions_validation_passes() -> None:
    manifest = {
        "data_quality": {
            "overall_status": "warn",
            "severity_levels": ["info", "warn", "fail"],
            "findings": [
                {
                    "category": "ppt",
                    "severity": "warn",
                    "code": "PPT_LINKS_NOT_REFRESHED",
                    "message": "PPT links were not refreshed.",
                }
            ],
            "counts": {
                "total_findings": 1,
                "by_severity": {"info": 0, "warn": 1, "fail": 0},
                "by_category": {"ppt": {"info": 0, "warn": 1, "fail": 0, "total": 1}},
            },
            "recommended_actions": [
                {
                    "category": "ppt",
                    "severity": "warn",
                    "action": "Refresh links via COM and regenerate slides.",
                }
            ],
        }
    }

    is_valid, error = validate_manifest_data_quality(manifest)

    assert is_valid is True
    assert error is None


def test_manifest_data_quality_validation_rejects_missing_recommended_actions() -> None:
    manifest = {
        "data_quality": {
            "overall_status": "info",
            "severity_levels": ["info", "warn", "fail"],
            "findings": [],
            "counts": {
                "total_findings": 0,
                "by_severity": {"info": 0, "warn": 0, "fail": 0},
                "by_category": {},
            },
        }
    }

    is_valid, error = validate_manifest_data_quality(manifest)

    assert is_valid is False
    assert error == "Manifest data_quality is missing required recommended_actions field."


def test_manifest_data_quality_validation_rejects_incomplete_recommended_action_entry() -> None:
    manifest = {
        "data_quality": {
            "overall_status": "fail",
            "severity_levels": ["info", "warn", "fail"],
            "findings": [],
            "counts": {
                "total_findings": 1,
                "by_severity": {"info": 0, "warn": 0, "fail": 1},
                "by_category": {},
            },
            "recommended_actions": [
                {
                    "category": "reconciliation",
                    "severity": "fail",
                }
            ],
        }
    }

    is_valid, error = validate_manifest_data_quality(manifest)

    assert is_valid is False
    assert error == "Manifest data_quality recommended_actions[0] must include non-empty action."


def test_manifest_data_quality_validation_rejects_unknown_action_severity() -> None:
    manifest = {
        "data_quality": {
            "overall_status": "warn",
            "severity_levels": ["info", "warn", "fail"],
            "findings": [],
            "counts": {
                "total_findings": 1,
                "by_severity": {"info": 0, "warn": 1, "fail": 0},
                "by_category": {},
            },
            "recommended_actions": [
                {
                    "category": "input",
                    "severity": "critical",
                    "action": "Correct source workbook headers.",
                }
            ],
        }
    }

    is_valid, error = validate_manifest_data_quality(manifest)

    assert is_valid is False
    assert (
        error
        == "Manifest data_quality recommended_actions[0].severity must be one of: info, warn, fail."
    )
