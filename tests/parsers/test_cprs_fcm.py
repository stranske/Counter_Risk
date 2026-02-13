"""Tests for CPRS-FCM parser."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest

from counter_risk.parsers.cprs_fcm import parse_fcm_totals, parse_futures_detail

_ALL_PROGRAMS_FIXTURE = "MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx"
_EX_TREND_FIXTURE = "MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx"
_TREND_FIXTURE = "MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx"

_TOTAL_COLUMNS = (
    "counterparty",
    "TIPS",
    "Treasury",
    "Equity",
    "Commodity",
    "Currency",
    "Notional",
    "NotionalChange",
)

_FUTURES_COLUMNS = ("account", "description", "class", "fcm", "clearing_house", "notional")


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

    @property
    def empty(self) -> bool:
        return len(self._rows) == 0

    @property
    def loc(self) -> _LocIndexer:
        return _LocIndexer(self)

    def __setitem__(self, key: str, value: Any) -> None:
        if key not in self.columns:
            self.columns.append(key)
        for row in self._rows:
            row[key] = value

    def astype(self, dtypes: dict[str, str]) -> _FakeDataFrame:
        for row in self._rows:
            for column, dtype in dtypes.items():
                if column not in row:
                    continue
                if dtype == "float64":
                    row[column] = float(row[column])
                elif dtype == "int64":
                    row[column] = int(row[column])
                elif dtype == "string":
                    row[column] = str(row[column])
        return self

    def to_records(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._rows]


class _LocIndexer:
    def __init__(self, frame: _FakeDataFrame) -> None:
        self._frame = frame

    def __getitem__(self, key: tuple[slice, list[str]]) -> _FakeDataFrame:
        _rows_slice, columns = key
        records = [{column: row.get(column) for column in columns} for row in self._frame._rows]
        return _FakeDataFrame(records=records, columns=columns)


@pytest.fixture
def fake_pandas(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = types.SimpleNamespace(DataFrame=_FakeDataFrame)
    monkeypatch.setitem(sys.modules, "pandas", fake_module)


def _fixture(name: str) -> Path:
    return Path("tests/fixtures") / name


def test_parse_fcm_totals_all_programs_non_empty_and_stable_columns(fake_pandas: None) -> None:
    df = parse_fcm_totals(_fixture(_ALL_PROGRAMS_FIXTURE))

    assert tuple(df.columns) == _TOTAL_COLUMNS
    assert not df.empty
    records = df.to_records()
    assert any(row["counterparty"] == "Morgan Stanley" for row in records)


def test_parse_fcm_totals_ex_trend_non_empty_and_stable_columns(fake_pandas: None) -> None:
    df = parse_fcm_totals(_fixture(_EX_TREND_FIXTURE))

    assert tuple(df.columns) == _TOTAL_COLUMNS
    assert not df.empty
    records = df.to_records()
    assert all(row["counterparty"] for row in records)


def test_parse_fcm_totals_trend_is_empty(fake_pandas: None) -> None:
    df = parse_fcm_totals(_fixture(_TREND_FIXTURE))

    assert tuple(df.columns) == _TOTAL_COLUMNS
    assert df.empty


def test_parse_futures_detail_all_programs_non_empty_and_stable_columns(
    fake_pandas: None,
) -> None:
    df = parse_futures_detail(_fixture(_ALL_PROGRAMS_FIXTURE))

    assert tuple(df.columns) == _FUTURES_COLUMNS
    assert not df.empty
    records = df.to_records()
    assert all(row["fcm"] == "Morgan Stanley" for row in records)


def test_parse_futures_detail_ex_trend_is_empty(fake_pandas: None) -> None:
    df = parse_futures_detail(_fixture(_EX_TREND_FIXTURE))

    assert tuple(df.columns) == _FUTURES_COLUMNS
    assert df.empty


def test_parse_futures_detail_trend_non_empty_and_stable_columns(fake_pandas: None) -> None:
    df = parse_futures_detail(_fixture(_TREND_FIXTURE))

    assert tuple(df.columns) == _FUTURES_COLUMNS
    assert not df.empty
    records = df.to_records()
    assert any(row["class"] == "Currency" for row in records)
