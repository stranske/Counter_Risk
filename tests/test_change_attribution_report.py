"""Unit tests for change attribution report generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.reports.change_attribution import (
    attribute_changes,
    write_change_attribution_csv,
    write_change_attribution_markdown,
)


def test_attribute_changes_labels_unmatched_current_rows() -> None:
    current = [{"counterparty": "New Desk", "Notional": 50.0}]
    prior = [{"counterparty": "Legacy Desk", "Notional": 25.0}]

    report = attribute_changes(current, prior)
    row = report["rows"][0]

    assert row["counterparty"] == "New Desk"
    assert row["matched_prior_counterparty"] == ""
    assert row["is_unmatched"] is True
    assert row["confidence"] == "Low"
    assert row["match_type"] == "unmatched"
    assert row["attribution_reason"] == "new_or_unmatched_current_row"
    assert report["summary"]["unmatched_rows"] == 1


def test_attribute_changes_computes_notional_change_for_matched_rows() -> None:
    current = [{"counterparty": "Desk A", "Notional": 125.0}]
    prior = [{"counterparty": "Desk A", "Notional": 100.0}]

    report = attribute_changes(current, prior)
    row = report["rows"][0]

    assert row["matched_prior_counterparty"] == "Desk A"
    assert row["notional_change"] == 25.0
    assert row["is_unmatched"] is False


def test_attribute_changes_assigns_high_confidence_for_exact_match_and_clean_delta() -> None:
    current = [{"counterparty": "Desk A", "Notional": 125.0, "NotionalChange": 25.0}]
    prior = [{"counterparty": "Desk A", "Notional": 100.0}]

    report = attribute_changes(current, prior)
    row = report["rows"][0]

    assert row["match_type"] == "exact"
    assert row["confidence"] == "High"
    assert row["is_low_confidence"] is False


def test_attribute_changes_assigns_medium_confidence_for_exact_match_with_non_clean_delta() -> None:
    current = [{"counterparty": "Desk A", "Notional": 125.0, "NotionalChange": 24.0}]
    prior = [{"counterparty": "Desk A", "Notional": 100.0}]

    report = attribute_changes(current, prior)
    row = report["rows"][0]

    assert row["match_type"] == "exact"
    assert row["attribution_reason"] == "exact_key_match"
    assert row["confidence"] == "Medium"
    assert row["is_low_confidence"] is False


def test_attribute_changes_assigns_low_confidence_for_fuzzy_match() -> None:
    current = [{"counterparty": "Morgan Stanley Prime", "Notional": 125.0}]
    prior = [{"counterparty": "Morgan Stanley", "Notional": 120.0}]

    report = attribute_changes(current, prior)
    row = report["rows"][0]

    assert row["match_type"] == "fuzzy"
    assert row["confidence"] == "Low"
    assert row["is_low_confidence"] is True


def test_attribute_changes_assigns_medium_confidence_for_normalized_match() -> None:
    current = [{"counterparty": "Desk-A", "Notional": 125.0}]
    prior = [{"counterparty": "desk a", "Notional": 120.0}]

    report = attribute_changes(current, prior)
    row = report["rows"][0]

    assert row["match_type"] == "normalized"
    assert row["confidence"] == "Medium"
    assert row["attribution_reason"] == "normalized_name_match_minor_differences"
    assert row["is_low_confidence"] is False


def test_attribute_changes_downgrades_normalized_match_when_difference_is_not_minor() -> None:
    current = [{"counterparty": "a----b----c----d", "Notional": 125.0}]
    prior = [{"counterparty": "abcd", "Notional": 120.0}]

    report = attribute_changes(current, prior)
    row = report["rows"][0]

    assert row["match_type"] == "normalized"
    assert row["confidence"] == "Low"
    assert row["attribution_reason"] == "normalized_name_match_requires_review"
    assert row["is_low_confidence"] is True


def test_attribute_changes_handles_missing_prior_data_gracefully() -> None:
    current = [{"counterparty": "Desk A", "Notional": 10.0}]

    report = attribute_changes(current, prior_df=[])
    row = report["rows"][0]

    assert report["summary"]["total_prior_rows"] == 0
    assert report["summary"]["unmatched_rows"] == 1
    assert report["summary"]["low_confidence_rows"] == 1
    assert report["summary"]["unattributed_remainder"] == 10.0
    assert row["attribution_reason"] == "missing_prior_data"


@pytest.mark.parametrize(
    ("current", "prior", "expected_reason", "expected_match_type"),
    [
        (
            [{"counterparty": "Morgan Stanley Prime", "Notional": 125.0}],
            [{"counterparty": "Morgan Stanley", "Notional": 120.0}],
            "fuzzy_name_match_partial_similarity",
            "fuzzy",
        ),
        (
            [{"counterparty": "a----b----c----d", "Notional": 125.0}],
            [{"counterparty": "abcd", "Notional": 120.0}],
            "normalized_name_match_requires_review",
            "normalized",
        ),
        (
            [{"counterparty": "Desk A", "Notional": 10.0}],
            [],
            "missing_prior_data",
            "unmatched",
        ),
    ],
)
def test_attribute_changes_low_confidence_criteria(
    current: list[dict[str, float | str]],
    prior: list[dict[str, float | str]],
    expected_reason: str,
    expected_match_type: str,
) -> None:
    report = attribute_changes(current, prior)
    row = report["rows"][0]

    assert row["match_type"] == expected_match_type
    assert row["attribution_reason"] == expected_reason
    assert row["confidence"] == "Low"
    assert row["is_low_confidence"] is True


def test_change_attribution_outputs_write_csv_and_markdown(tmp_path: Path) -> None:
    report = attribute_changes(
        [{"counterparty": "Desk A", "Notional": 125.0}],
        [{"counterparty": "Desk A", "Notional": 100.0}],
    )

    csv_path = tmp_path / "change_attribution.csv"
    md_path = tmp_path / "change_attribution.md"

    write_change_attribution_csv(report=report, path=csv_path)
    write_change_attribution_markdown(report=report, path=md_path)

    assert csv_path.exists()
    assert "counterparty,matched_prior_counterparty" in csv_path.read_text(encoding="utf-8")
    assert md_path.exists()
    assert "# Change Attribution" in md_path.read_text(encoding="utf-8")
