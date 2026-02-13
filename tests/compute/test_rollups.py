"""Tests for computation rollups."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from counter_risk.compute.rollups import (
    compute_notional_breakdown,
    compute_totals,
    top_changes,
    top_exposures,
)
from counter_risk.parsers.cprs_fcm import parse_fcm_totals

_FRACTION_TOLERANCE = 1e-9


def _as_records(table: Any) -> list[dict[str, Any]]:
    if hasattr(table, "to_dict"):
        return cast(list[dict[str, Any]], table.to_dict(orient="records"))
    return [dict(row) for row in table]


def _fixture(name: str) -> Path:
    return Path("tests/fixtures") / name


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


def test_top_exposures_is_deterministic_for_fixture_input() -> None:
    pytest.importorskip("pandas")
    totals = parse_fcm_totals(
        _fixture("MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx")
    )
    totals_rows = _as_records(totals)

    exposures = [
        {
            "counterparty": row["counterparty"],
            "asset_class": asset_class,
            "notional": row[asset_class],
        }
        for row in totals_rows
        for asset_class in ("TIPS", "Treasury", "Equity", "Commodity", "Currency")
    ]

    first = _as_records(top_exposures(exposures, n=10))
    second = _as_records(top_exposures(list(reversed(exposures)), n=10))

    assert first == second


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
