"""Unit tests for change attribution report generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.reports.change_attribution import (
    _first_float,
    _optional_float,
    attribute_changes,
    render_change_attribution_markdown,
    write_change_attribution_csv,
    write_change_attribution_markdown,
)


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", float("nan"), float("inf"), -float("inf")])
def test_float_parsers_reject_non_finite_values(value: str | float) -> None:
    assert _first_float({"Notional": value}, ("Notional", "notional")) == 0.0
    assert _first_float({"Notional": value, "notional": 12.5}, ("Notional", "notional")) == 12.5
    assert _optional_float({"NotionalChange": value}, ("NotionalChange",)) is None
    # An invalid supplied delta is absent; a later alias must not replace it.
    assert (
        _optional_float(
            {"NotionalChange": value, "notional_change": 25.0},
            ("NotionalChange", "notional_change"),
        )
        is None
    )


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("invalid_source", ["current", "prior", "delta", "unmatched"])
def test_attribute_changes_non_finite_inputs_produce_finite_report(
    value: str | float, invalid_source: str
) -> None:
    current: dict[str, str | float] = {"counterparty": "Desk A", "Notional": 125.0}
    prior: dict[str, str | float] = {"counterparty": "Desk A", "Notional": 100.0}
    if invalid_source in {"current", "unmatched"}:
        current["Notional"] = value
    elif invalid_source == "prior":
        prior["Notional"] = value
    else:
        current["NotionalChange"] = value

    report = attribute_changes([current], [] if invalid_source == "unmatched" else [prior])
    row = report["rows"][0]
    expected_current = 0.0 if invalid_source in {"current", "unmatched"} else 125.0
    expected_prior = 0.0 if invalid_source in {"prior", "unmatched"} else 100.0
    assert row["current_notional"] == expected_current
    assert row["prior_notional"] == expected_prior
    assert row["notional_change"] == expected_current - expected_prior
    assert report["summary"]["unattributed_remainder"] == 0.0
    if invalid_source == "delta":
        assert row["confidence"] == "High"  # Same as an absent optional delta.
    markdown = render_change_attribution_markdown(report).lower()
    assert "nan" not in markdown
    assert "inf" not in markdown


@pytest.mark.parametrize("value", [0.0, -12.5, 25.0, "0", "-12.5", "25"])
def test_float_parsers_preserve_finite_values(value: str | float) -> None:
    assert _first_float({"notional": value}, ("notional",)) == float(value)
    assert _optional_float({"notional_change": value}, ("notional_change",)) == float(value)


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
    assert row["review_label"] == "UNMATCHED|LOW_CONFIDENCE"
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
    assert row["review_label"] == "NONE"


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
    assert "review_label" in csv_path.read_text(encoding="utf-8")
    assert md_path.exists()
    assert "# Change Attribution" in md_path.read_text(encoding="utf-8")


def test_change_attribution_outputs_explicitly_label_unmatched_and_low_confidence(
    tmp_path: Path,
) -> None:
    report = attribute_changes(
        [{"counterparty": "New Desk", "Notional": 50.0}],
        [{"counterparty": "Legacy Desk", "Notional": 25.0}],
    )
    csv_path = tmp_path / "change_attribution.csv"
    md_path = tmp_path / "change_attribution.md"

    write_change_attribution_csv(report=report, path=csv_path)
    write_change_attribution_markdown(report=report, path=md_path)

    csv_text = csv_path.read_text(encoding="utf-8")
    md_text = md_path.read_text(encoding="utf-8")
    assert "UNMATCHED|LOW_CONFIDENCE" in csv_text
    assert "UNMATCHED|LOW_CONFIDENCE" in md_text
