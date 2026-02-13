"""Tests for computation rollups."""

from __future__ import annotations

from typing import Any

import pytest

from counter_risk.compute.rollups import (
    compute_notional_breakdown,
    compute_totals,
    top_changes,
    top_exposures,
)

_FRACTION_TOLERANCE = 1e-9


def _as_records(table: Any) -> list[dict[str, Any]]:
    if hasattr(table, "to_dict"):
        return table.to_dict(orient="records")
    return [dict(row) for row in table]


def test_compute_notional_breakdown_sums_to_one_multi_asset() -> None:
    exposures = [
        {"counterparty": "A", "asset_class": "Cash", "notional": 100.0},
        {"counterparty": "B", "asset_class": "Equity", "notional": 50.0},
        {"counterparty": "C", "asset_class": "Treasury", "notional": 50.0},
    ]

    breakdown = compute_notional_breakdown(exposures)

    assert breakdown
    assert sum(breakdown.values()) == pytest.approx(1.0, abs=_FRACTION_TOLERANCE)


def test_compute_notional_breakdown_empty_input() -> None:
    assert compute_notional_breakdown([]) == {}


def test_compute_notional_breakdown_single_asset_class() -> None:
    exposures = [
        {"counterparty": "A", "asset_class": "Cash", "notional": 12.5},
        {"counterparty": "B", "asset_class": "Cash", "notional": 7.5},
    ]

    breakdown = compute_notional_breakdown(exposures)

    assert breakdown == {"Cash": 1.0}


def test_compute_totals_aggregates_counterparty_and_asset_class() -> None:
    exposures = [
        {
            "counterparty": "A",
            "asset_class": "Cash",
            "notional": 10.0,
            "prior_notional": 4.0,
        },
        {
            "counterparty": "A",
            "asset_class": "Equity",
            "notional": 5.0,
            "prior_notional": 1.0,
        },
        {
            "counterparty": "B",
            "asset_class": "Cash",
            "notional": 6.0,
            "prior_notional": 3.0,
        },
    ]

    totals = _as_records(compute_totals(exposures))

    assert {
        "group_type",
        "group_name",
        "notional",
        "prior_notional",
        "notional_change",
    } == set(totals[0].keys())

    assert {(row["group_type"], row["group_name"], row["notional"]) for row in totals} == {
        ("counterparty", "A", 15.0),
        ("counterparty", "B", 6.0),
        ("asset_class", "Cash", 16.0),
        ("asset_class", "Equity", 5.0),
    }


def test_top_exposures_is_deterministic_for_ties() -> None:
    exposures = [
        {"counterparty": "Bravo", "asset_class": "Equity", "notional": 100.0},
        {"counterparty": "Alpha", "asset_class": "Treasury", "notional": 100.0},
        {"counterparty": "Charlie", "asset_class": "Cash", "notional": 50.0},
    ]

    first = _as_records(top_exposures(exposures, n=3))
    second = _as_records(top_exposures(exposures, n=3))

    assert first == second
    assert [row["counterparty"] for row in first] == ["Alpha", "Bravo", "Charlie"]


def test_top_changes_sorts_by_absolute_change() -> None:
    totals = [
        {
            "group_type": "counterparty",
            "group_name": "A",
            "notional": 110.0,
            "prior_notional": 100.0,
            "notional_change": 10.0,
        },
        {
            "group_type": "counterparty",
            "group_name": "B",
            "notional": 60.0,
            "prior_notional": 100.0,
            "notional_change": -40.0,
        },
        {
            "group_type": "asset_class",
            "group_name": "Cash",
            "notional": 50.0,
            "prior_notional": 30.0,
            "notional_change": 20.0,
        },
    ]

    top = _as_records(top_changes(totals, n=2))

    assert [row["group_name"] for row in top] == ["B", "Cash"]
