"""Tests for CPRS-CH parser."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest

from counter_risk.parsers.cprs_ch import parse_cprs_ch

_ALL_PROGRAMS_FIXTURE = "CPRS-CH Fixture - All Programs.xlsx"
_EX_TREND_FIXTURE = "CPRS-CH Fixture - Ex Trend.xlsx"
_TREND_FIXTURE = "CPRS-CH Fixture - Trend.xlsx"
_NUMERIC_COLUMNS = (
    "Cash",
    "TIPS",
    "Treasury",
    "Equity",
    "Commodity",
    "Currency",
    "Notional",
)
_STABLE_COLUMNS = (
    "Segment",
    "Counterparty",
    "Cash",
    "TIPS",
    "Treasury",
    "Equity",
    "Commodity",
    "Currency",
    "Notional",
    "NotionalChangeFromPriorMonth",
    "AnnualizedVolatility",
    "SourceRow",
)


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


def test_parse_all_programs_variant(fake_pandas: None) -> None:
    df = parse_cprs_ch(_fixture(_ALL_PROGRAMS_FIXTURE))

    assert not df.empty
    records = df.to_records()
    assert any(row["Segment"] == "swaps" for row in records)
    assert any(row["Segment"] == "repo" for row in records)
    assert any(row["Segment"] == "futures_cdx" for row in records)
    assert tuple(df.columns) == _STABLE_COLUMNS

    sample = records[0]
    for column in _NUMERIC_COLUMNS:
        assert isinstance(sample[column], float)


def test_parse_ex_trend_variant(fake_pandas: None) -> None:
    df = parse_cprs_ch(_fixture(_EX_TREND_FIXTURE))

    records = df.to_records()
    segments = {row["Segment"] for row in records}
    assert "swaps" in segments
    assert "repo" in segments


def test_parse_trend_variant_maps_swaps_to_futures(fake_pandas: None) -> None:
    df = parse_cprs_ch(_fixture(_TREND_FIXTURE))

    records = df.to_records()
    assert {row["Segment"] for row in records} == {"futures"}


def test_parse_cprs_ch_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        parse_cprs_ch(Path("tests/fixtures/does-not-exist.xlsx"))
