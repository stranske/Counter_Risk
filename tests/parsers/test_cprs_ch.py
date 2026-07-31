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


def _build_real_shape_workbook(tmp_path: Path, name: str) -> Path:
    """Build a minimal workbook reproducing two real-world layout quirks seen in
    actual MOSERS exports:

    1. A segment marker label (e.g. "Swaps") sharing its row with the first real
       data row (label in column A, data starting in column B).
    2. A "Total by Counterparty/Clearing House" rollup section where every row is
       *also* stamped with a shorter "Total by Counterparty" tag in column A (a
       real-world formatting artifact), plus trailing footer/annotation rows
       ("Total Current Exposure", "MOSERS Program", "Notional Breakdown",
       asterisked footnotes) that must not be parsed as counterparty rows.
    """
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "CPRS-CH"

    sheet["A1"] = "Counterparty Risk Summary"
    sheet["A2"] = "Futures - Clearing House"
    sheet["A3"] = "As of 1.31.2026"
    sheet["B5"] = "Counterparty/ \nClearing House"
    sheet["K5"] = "Notional"
    sheet["D6"] = "Cash"
    sheet["E6"] = "TIPS"
    sheet["F6"] = "Treasury"
    sheet["G6"] = "Equity"
    sheet["H6"] = "Commodity"
    sheet["I6"] = "Currency"

    # Swaps: label shares row 7 with the first data row (Citigroup).
    sheet["A7"] = "Swaps"
    sheet["B7"] = "Citigroup"
    sheet["K7"] = 111.0
    sheet["B8"] = "Bank of America, NA"
    sheet["K8"] = 222.0

    # Repo: label shares row 10 with the first data row (Nomura).
    sheet["A10"] = "Repo"
    sheet["B10"] = "Nomura"
    sheet["K10"] = 33.0

    # Rollup section: marker on its own row, but every data row also carries a
    # shorter "Total by Counterparty" tag in column A.
    sheet["B13"] = (
        "Total by Counterparty/Clearing House (This is not the legal obligation exposure)"
    )
    sheet["A14"] = "Total by Counterparty"
    sheet["B14"] = "Citigroup"
    sheet["K14"] = 111.0
    sheet["A15"] = "Total by Counterparty"
    sheet["B15"] = "Bank of America, NA"
    sheet["K15"] = 222.0
    sheet["A16"] = "Total by Counterparty"
    sheet["B16"] = "Nomura"
    sheet["K16"] = 33.0

    # Footer/annotation noise that must be excluded.
    sheet["B17"] = "Total Current Exposure"
    sheet["B18"] = "MOSERS Program"
    sheet["K18"] = 366.0
    sheet["B19"] = "Notional Breakdown"
    sheet["B20"] = "*** Does not include cash."
    # Some real exports wrap the footnote in a literal straight-quote pair.
    sheet["B21"] = '"***Does not include cash"'

    path = tmp_path / name
    workbook.save(path)
    return path


def test_parse_cprs_ch_includes_first_row_sharing_segment_label(
    tmp_path: Path, fake_pandas: None
) -> None:
    """Regression test: a segment label sharing its row with the first data row
    (e.g. "Swaps" in column A, "Citigroup" in column B on the same row) must not
    drop that first row."""
    path = _build_real_shape_workbook(tmp_path, "shared_row.xlsx")
    df = parse_cprs_ch(path)
    records = df.to_records()

    swaps_names = {row["Counterparty"] for row in records if row["Segment"] == "swaps"}
    assert "Citigroup" in swaps_names

    repo_names = {row["Counterparty"] for row in records if row["Segment"] == "repo"}
    assert "Nomura" in repo_names


def test_parse_cprs_ch_totals_section_ignores_per_row_tag_and_footer_noise(
    tmp_path: Path, fake_pandas: None
) -> None:
    """Regression test: the rollup section's real counterparty rows must survive
    (even though every row repeats a shorter "Total by Counterparty" tag in
    column A that could be mistaken for a second section marker), and footer/
    annotation rows must not appear as counterparty data."""
    path = _build_real_shape_workbook(tmp_path, "totals_noise.xlsx")
    df = parse_cprs_ch(path)
    records = df.to_records()

    totals = [row for row in records if row["Segment"] == "totals"]
    totals_names = {row["Counterparty"] for row in totals}
    assert totals_names == {"Citigroup", "Bank of America, NA", "Nomura"}

    all_names = {row["Counterparty"] for row in records}
    assert "Total Current Exposure" not in all_names
    assert "MOSERS Program" not in all_names
    assert "Notional Breakdown" not in all_names
    assert "*** Does not include cash." not in all_names
    assert '"***Does not include cash"' not in all_names


def test_parse_cprs_ch_finds_totals_marker_shifted_to_column_c(
    tmp_path: Path, fake_pandas: None
) -> None:
    """Regression test: a real December 2025 export places the "Total by
    Counterparty/Clearing House" rollup marker in column C (the same column that
    holds counterparty names in that file) with columns A and B both empty on
    that row — unlike the other segment markers (Swaps/Repo/Futures), which sit
    in column B. Before this fix, the marker went undetected and the entire
    rollup section silently merged into the preceding segment, corrupting any
    aggregate computed from "all rows" (double-counting, since the rollup
    restates the segment rows)."""
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "CPRS-CH"

    sheet["C5"] = "Counterparty/ \nClearing House"
    sheet["K5"] = "Notional"

    sheet["B7"] = "Swaps"
    sheet["C7"] = "Citigroup"
    sheet["K7"] = 111.0

    sheet["B9"] = "Repo"
    sheet["C9"] = "Nomura"
    sheet["K9"] = 33.0

    # Rollup marker in column C only (A and B empty on this row).
    sheet["C11"] = (
        "Total by Counterparty/Clearing House (This is not the legal obligation exposure)"
    )
    sheet["B12"] = "Total by Counterparty"
    sheet["C12"] = "Citigroup"
    sheet["K12"] = 111.0
    sheet["B13"] = "Total by Counterparty"
    sheet["C13"] = "Nomura"
    sheet["K13"] = 33.0

    path = tmp_path / "column_c_marker.xlsx"
    workbook.save(path)

    df = parse_cprs_ch(path)
    records = df.to_records()

    totals = [row for row in records if row["Segment"] == "totals"]
    assert {row["Counterparty"] for row in totals} == {"Citigroup", "Nomura"}
    assert sum(row["Notional"] for row in totals) == pytest.approx(144.0)

    # The overall sum across every row must not double-count the rollup section.
    assert sum(row["Notional"] for row in records) == pytest.approx(288.0)


def test_parse_cprs_ch_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        parse_cprs_ch(Path("tests/fixtures/does-not-exist.xlsx"))


def test_parse_cprs_ch_raises_clear_error_when_pandas_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, "pandas", raising=False)

    real_import = __import__

    def _import_without_pandas(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "pandas":
            raise ModuleNotFoundError("No module named 'pandas'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _import_without_pandas)

    with pytest.raises(ModuleNotFoundError, match="requires pandas"):
        parse_cprs_ch(_fixture(_ALL_PROGRAMS_FIXTURE))
