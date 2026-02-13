"""Tests for computation rollups."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

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
        return table.to_dict(orient="records")
    return [dict(row) for row in table]


class _FakeDataFrame:
    def __init__(
        self,
        records: list[dict[str, Any]] | None = None,
        columns: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        self._rows = [dict(row) for row in (records or [])]
        if columns is not None:
            self.columns: list[str] = list(columns)
        elif self._rows:
            self.columns = list(self._rows[0].keys())
        else:
            self.columns = []

    def __setitem__(self, key: str, value: Any) -> None:
        if key not in self.columns:
            self.columns.append(key)
        for row in self._rows:
            row[key] = value

    @property
    def loc(self) -> _LocIndexer:
        return _LocIndexer(self)

    def astype(self, dtypes: dict[str, str]) -> _FakeDataFrame:
        for row in self._rows:
            for column, dtype in dtypes.items():
                if column not in row:
                    continue
                if dtype == "float64":
                    row[column] = float(row[column])
                elif dtype == "string":
                    row[column] = str(row[column])
        return self

    def to_dict(self, orient: str = "records") -> list[dict[str, Any]]:
        if orient != "records":
            raise ValueError("Only records orient is supported in tests")
        return [dict(row) for row in self._rows]


class _LocIndexer:
    def __init__(self, frame: _FakeDataFrame) -> None:
        self._frame = frame

    def __getitem__(self, key: tuple[slice, list[str]]) -> _FakeDataFrame:
        _rows_slice, columns = key
        records = [{column: row.get(column) for column in columns} for row in self._frame._rows]
        return _FakeDataFrame(records=records, columns=columns)


def _fixture(name: str) -> Path:
    return Path("tests/fixtures") / name


@pytest.fixture
def fake_pandas(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = types.SimpleNamespace(DataFrame=_FakeDataFrame)
    monkeypatch.setitem(sys.modules, "pandas", fake_module)


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


def test_top_exposures_is_deterministic_for_fixture_input(fake_pandas: None) -> None:
    totals = parse_fcm_totals(_fixture("MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx"))
    totals_rows = _as_records(totals)

    exposures = [
        {"counterparty": row["counterparty"], "asset_class": asset_class, "notional": row[asset_class]}
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
