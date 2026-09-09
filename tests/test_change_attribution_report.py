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


@pytest.mark.parametrize("reverse_prior", [False, True])
@pytest.mark.parametrize(
    ("current_name", "prior_names", "match_type", "confidence"),
    [
        ("JPMorgan", ("JPMorgan", "JPMorgan"), "exact", "High"),
        ("JP-Morgan", ("JPMorgan", "jp morgan"), "normalized", "Medium"),
        ("Morgan Stanley Prime", ("Morgan Stanley", "morgan stanley"), "fuzzy", "Low"),
    ],
)
def test_attribute_changes_aggregates_prior_counterparty_rows(
    current_name: str,
    prior_names: tuple[str, str],
    match_type: str,
    confidence: str,
    reverse_prior: bool,
) -> None:
    prior = [
        {"counterparty": prior_names[0], "Notional": 100.0, "account": "A"},
        {"counterparty": prior_names[1], "Notional": 50.0, "account": "B"},
        {"counterparty": "Unrelated Bank", "Notional": 900.0},
    ]
    if reverse_prior:
        prior.reverse()
    report = attribute_changes(
        [{"counterparty": current_name, "Notional": 150.0, "NotionalChange": 0.0}],
        prior,
    )
    row = report["rows"][0]
    assert row["prior_notional"] == 150.0
    assert row["notional_change"] == 0.0
    assert row["match_type"] == match_type
    assert row["confidence"] == confidence
    assert report["summary"]["total_prior_rows"] == 3
    assert report["summary"]["unattributed_remainder"] == 0.0
    assert "| 150.000000 | 150.000000 | 0.000000 |" in render_change_attribution_markdown(report)


@pytest.mark.parametrize(("supplied_delta", "confidence"), [(25.0, "High"), (125.0, "Medium")])
def test_aggregated_prior_notional_controls_delta_confidence(
    supplied_delta: float, confidence: str
) -> None:
    report = attribute_changes(
        [{"counterparty": "JPMorgan", "Notional": 175.0, "NotionalChange": supplied_delta}],
        [
            {"counterparty": "JPMorgan", "Notional": 100.0},
            {"counterparty": "JPMorgan", "Notional": 50.0},
        ],
    )
    row = report["rows"][0]
    assert row["prior_notional"] == 150.0
    assert row["notional_change"] == 25.0
    assert row["confidence"] == confidence


def test_prior_aggregation_preserves_exact_match_precedence_and_signed_notionals() -> None:
    report = attribute_changes(
        [{"counterparty": "Desk A", "Notional": 75.0}],
        [
            {"counterparty": "Desk A", "Notional": 100.0},
            {"counterparty": "Desk A", "Notional": -25.0},
            {"counterparty": "desk-a", "Notional": 900.0},
        ],
    )
    row = report["rows"][0]
    assert row["prior_notional"] == 75.0
    assert row["notional_change"] == 0.0
    assert row["match_type"] == "exact"
    assert row["matched_prior_counterparty"] == "Desk A"


def test_aggregated_prior_group_is_not_reused_for_a_later_fuzzy_match() -> None:
    report = attribute_changes(
        [
            {"counterparty": "Morgan Stanley", "Notional": 150.0},
            {"counterparty": "Morgan Stanley Prime", "Notional": 25.0},
        ],
        [
            {"counterparty": "Morgan Stanley", "Notional": 100.0},
            {"counterparty": "Morgan Stanley", "Notional": 50.0},
        ],
    )
    exact, unmatched = report["rows"]
    assert exact["prior_notional"] == 150.0
    assert unmatched["prior_notional"] == 0.0
    assert unmatched["is_unmatched"] is True
    assert report["summary"]["unmatched_rows"] == 1
    assert report["summary"]["unattributed_remainder"] == 25.0


@pytest.mark.parametrize("reverse_current", [False, True])
@pytest.mark.parametrize(
    ("current_name", "prior_name", "match_type"),
    [
        ("Desk A", "Desk A", "exact"),
        ("Desk-A", "desk a", "normalized"),
        ("Morgan Stanley Prime", "Morgan Stanley", "fuzzy"),
    ],
)
def test_split_current_conservation(
    reverse_current: bool, current_name: str, prior_name: str, match_type: str
) -> None:
    prior = [{"counterparty": prior_name, "Notional": 250.0}]
    single = [{"counterparty": current_name, "Notional": 300.0, "NotionalChange": 50.0}]
    split = [
        {"counterparty": current_name, "Notional": 100.0, "NotionalChange": 25.0},
        {"counterparty": current_name, "Notional": 200.0, "NotionalChange": 25.0},
    ]
    if reverse_current:
        split.reverse()
    snapshot = [dict(row) for row in split]
    report = attribute_changes(split, prior)
    assert report["rows"] == attribute_changes(single, prior)["rows"]
    assert len(report["rows"]) == 1
    row = report["rows"][0]
    assert (row["current_notional"], row["prior_notional"], row["notional_change"]) == (
        300,
        250,
        50,
    )
    assert row["match_type"] == match_type
    assert report["summary"]["total_current_rows"] == 2  # Input count remains diagnostic.
    assert split == snapshot


@pytest.mark.parametrize(
    ("deltas", "confidence"),
    [
        ([25.0, 25.0], "High"),
        ([25.0, 24.0], "Medium"),
        ([25.0, None], "High"),
        ([None, 25.0], "High"),
        ([None, None], "High"),
    ],
)
def test_split_current_delta_confidence(deltas: list[float | None], confidence: str) -> None:
    report = attribute_changes(
        [
            {"counterparty": "Desk A", "Notional": amount, "NotionalChange": delta}
            for amount, delta in zip([100.0, 200.0], deltas, strict=True)
        ],
        [{"counterparty": "Desk A", "Notional": 250.0}],
    )
    assert len(report["rows"]) == 1
    assert report["rows"][0]["confidence"] == confidence


@pytest.mark.parametrize("reverse_current", [False, True])
def test_split_current_normalized_labels_are_deterministic(reverse_current: bool) -> None:
    current = [
        {"counterparty": "Desk-A", "Notional": 350.0, "NotionalChange": 75.0},
        {"counterparty": "DESK A", "Notional": -50.0, "NotionalChange": -25.0},
    ]
    if reverse_current:
        current.reverse()
    report = attribute_changes(current, [{"counterparty": "desk a", "Notional": 250.0}])
    assert len(report["rows"]) == 1
    row = report["rows"][0]
    assert row["counterparty"] == "DESK A"
    assert (row["current_notional"], row["prior_notional"], row["notional_change"]) == (
        300,
        250,
        50,
    )


def test_split_current_exact_and_normalized_matches_do_not_reuse_prior() -> None:
    current = [
        {"counterparty": name, "Notional": amount}
        for name, amount in [("Desk A", 100.0), ("Desk-A", 200.0)]
    ]
    prior = [
        {"counterparty": "Desk A", "Notional": 75.0},
        {"counterparty": "desk a", "Notional": 175.0},
    ]
    report = attribute_changes(current, prior)
    assert sum(row["current_notional"] for row in report["rows"]) == 300.0
    assert sum(row["prior_notional"] for row in report["rows"]) == 250.0
    assert sum(row["notional_change"] for row in report["rows"]) == 50.0


def test_fuzzy_match_cannot_consume_a_later_direct_normalized_match() -> None:
    report = attribute_changes(
        [
            {"counterparty": "Morgan Stanle", "Notional": 25.0},
            {"counterparty": "Morgan-Stanley", "Notional": 300.0},
        ],
        [{"counterparty": "Morgan Stanley", "Notional": 250.0}],
    )
    assert sum(row["prior_notional"] for row in report["rows"]) == 250.0
    assert report["rows"][0]["is_unmatched"] is True
