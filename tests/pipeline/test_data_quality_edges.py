"""Manifest findings retain actionable details for incomplete source metadata."""

import pytest

from counter_risk.pipeline.data_quality import _build_counts, build_data_quality


@pytest.mark.parametrize(
    ("entry", "issue"),
    [
        (
            {
                "error_type": "unmapped_counterparty",
                "raw_counterparties": [" z ", "A", "A", "B", "C"],
            },
            "unmapped_counterparty(A, B, C)",
        ),
        (
            {"error_type": "unmapped_counterparty", "raw_counterparties": "invalid"},
            "unmapped_counterparty",
        ),
        ({"data_source_context": " source workbook "}, "source workbook"),
        ({}, "reconciliation_gap"),
    ],
)
def test_reconciliation_details_use_safe_fallbacks(entry, issue: str) -> None:
    quality = build_data_quality(
        [],
        reconciliation_results={
            "status": "failed",
            "by_variant": {
                "invalid": None,
                "invalid-series": {"missing_series": "invalid"},
                "trend": {
                    "missing_series": [None, {"sheet": " ", "impacted_rows": "bad", **entry}]
                },
            },
        },
    )
    assert quality["overall_status"] == "fail"
    details = [row for row in quality["findings"] if row["code"] == "RECONCILIATION_GAP_DETAIL"]
    assert details == [
        {
            "category": "reconciliation",
            "severity": "fail",
            "code": "RECONCILIATION_GAP_DETAIL",
            "message": f"Reconciliation gap detail: variant=trend, sheet=unknown, impacted_rows=0, issue={issue}.",
        }
    ]


def test_failed_reconciliation_without_variant_map_still_reports_failure() -> None:
    quality = build_data_quality([], reconciliation_results={"status": "failed", "by_variant": []})
    assert [row["code"] for row in quality["findings"]] == ["RECONCILIATION_GAPS"]
    assert quality["overall_status"] == "fail"


@pytest.mark.parametrize(
    ("warning", "category", "severity"),
    [
        ({"code": "SOURCE_ERROR", "message": "Source unavailable"}, "pipeline", "fail"),
        ("Reconciliation requires attention", "reconciliation", "warn"),
        ("Mapping needs review", "mapping", "warn"),
        ("Source report date conflict: December versus January", "date", "warn"),
        ("Source report date override: December selected", "date", "warn"),
    ],
)
def test_warning_fallbacks_are_deduplicated_and_classified(
    warning, category: str, severity: str
) -> None:
    quality = build_data_quality([warning, warning, " ", {"message": ""}])
    assert len(quality["findings"]) == 1
    assert quality["findings"][0]["category"] == category
    assert quality["findings"][0]["severity"] == severity
    assert quality["counts"]["by_severity"][severity] == 1
    assert len(quality["recommended_actions"]) == 1


def test_unknown_severity_counts_as_warning_in_its_category() -> None:
    counts = _build_counts([{"category": "source", "severity": "invalid"}])
    assert counts == {
        "total_findings": 1,
        "by_severity": {"info": 0, "warn": 1, "fail": 0},
        "by_category": {"source": {"info": 0, "warn": 1, "fail": 0, "total": 1}},
    }


@pytest.mark.parametrize(
    ("message", "code", "severity"),
    [
        ("Repo cash overrides applied: 2", "REPO_CASH_OVERRIDES_APPLIED", "info"),
        ("Repo cash overrides file present but empty", "REPO_CASH_OVERRIDES_EMPTY", "warn"),
    ],
)
def test_cash_override_messages_keep_their_specific_codes(message, code, severity) -> None:
    quality = build_data_quality([message])
    assert quality["findings"] == [
        {"category": "cash", "severity": severity, "code": code, "message": message}
    ]
