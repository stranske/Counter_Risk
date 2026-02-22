"""Historical header extraction tests for reconciliation workbook scanning."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest

from counter_risk.pipeline import run as run_module


class _FakeCell:
    def __init__(self, value: Any = None) -> None:
        self.value = value


class _FakeWorksheet:
    def __init__(self, title: str) -> None:
        self.title = title
        self.max_row = 1
        self.max_column = 1
        self._cells: dict[tuple[int, int], _FakeCell] = {}

    def cell(self, row: int, column: int) -> _FakeCell:
        self.max_row = max(self.max_row, row)
        self.max_column = max(self.max_column, column)
        key = (row, column)
        if key not in self._cells:
            self._cells[key] = _FakeCell()
        return self._cells[key]

    def set_value(self, row: int, column: int, value: Any) -> None:
        self.cell(row=row, column=column).value = value


class _FakeWorkbook:
    def __init__(
        self,
        sheets: dict[str, _FakeWorksheet],
        *,
        sheetnames: list[str] | None = None,
    ) -> None:
        self._sheets = dict(sheets)
        self.sheetnames = list(sheetnames) if sheetnames is not None else list(sheets)
        self.closed = False

    def __getitem__(self, item: str) -> _FakeWorksheet:
        return self._sheets[item]

    def close(self) -> None:
        self.closed = True


def test_extract_historical_series_headers_uses_detected_header_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ignored_sheet = _FakeWorksheet("Ignored")
    ignored_sheet.set_value(1, 1, "Not a date header")

    target_sheet = _FakeWorksheet("Totals")
    target_sheet.set_value(1, 1, "metadata")
    target_sheet.set_value(2, 1, "still metadata")
    target_sheet.set_value(3, 1, "  As Of   Date ")
    target_sheet.set_value(3, 2, "Series A")
    target_sheet.set_value(3, 3, "Series B")

    workbook = _FakeWorkbook({"Ignored": ignored_sheet, "Totals": target_sheet})
    monkeypatch.setitem(
        sys.modules,
        "openpyxl",
        types.SimpleNamespace(load_workbook=lambda **_: workbook),
    )

    headers = run_module._extract_historical_series_headers_by_sheet(Path("unused.xlsx"))

    assert headers == {"Totals": ("Series A", "Series B")}
    assert workbook.closed is True


def test_extract_historical_series_headers_reraises_unexpected_errors_with_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_sheet = _FakeWorksheet("Totals")
    target_sheet.set_value(1, 1, "As Of Date")
    workbook = _FakeWorkbook({"Totals": target_sheet})
    monkeypatch.setitem(
        sys.modules,
        "openpyxl",
        types.SimpleNamespace(load_workbook=lambda **_: workbook),
    )

    def _raise_type_error(*, worksheet: Any, max_scan_rows: int = 25) -> int:
        del worksheet, max_scan_rows
        raise TypeError("bad worksheet payload")

    monkeypatch.setattr(run_module, "_find_historical_header_row", _raise_type_error)

    with pytest.raises(TypeError, match="sheet 'Totals'") as exc_info:
        run_module._extract_historical_series_headers_by_sheet(Path("unused.xlsx"))

    assert "unused.xlsx" in str(exc_info.value)
    assert "bad worksheet payload" in str(exc_info.value)
    assert workbook.closed is True


def test_extract_historical_series_headers_handles_expected_key_and_value_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_sheet = _FakeWorksheet("Totals")
    target_sheet.set_value(1, 1, "As Of Date")
    workbook = _FakeWorkbook(
        {"Totals": target_sheet},
        sheetnames=["MissingSheet", "Totals"],
    )
    monkeypatch.setitem(
        sys.modules,
        "openpyxl",
        types.SimpleNamespace(load_workbook=lambda **_: workbook),
    )

    def _raise_value_error(*, worksheet: Any, max_scan_rows: int = 25) -> int:
        del worksheet, max_scan_rows
        raise ValueError("header row not found")

    monkeypatch.setattr(run_module, "_find_historical_header_row", _raise_value_error)

    headers = run_module._extract_historical_series_headers_by_sheet(Path("unused.xlsx"))

    assert headers == {}
    assert workbook.closed is True


def test_extract_historical_series_headers_reraises_unexpected_workbook_load_errors_with_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _load_workbook(*, filename: Path, read_only: bool, data_only: bool) -> _FakeWorkbook:
        del read_only, data_only
        raise TypeError(f"bad workbook payload for {filename}")

    monkeypatch.setitem(
        sys.modules, "openpyxl", types.SimpleNamespace(load_workbook=_load_workbook)
    )

    with pytest.raises(
        TypeError, match="Unexpected error while loading historical workbook"
    ) as exc_info:
        run_module._extract_historical_series_headers_by_sheet(Path("unused.xlsx"))

    assert "unused.xlsx" in str(exc_info.value)
    assert "bad workbook payload" in str(exc_info.value)


def test_extract_historical_series_headers_reraises_unexpected_sheet_load_errors_with_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _TypeErrorWorkbook(_FakeWorkbook):
        def __getitem__(self, item: str) -> _FakeWorksheet:
            raise TypeError(f"broken workbook for {item}")

    workbook = _TypeErrorWorkbook({}, sheetnames=["Totals"])
    monkeypatch.setitem(
        sys.modules,
        "openpyxl",
        types.SimpleNamespace(load_workbook=lambda **_: workbook),
    )

    with pytest.raises(TypeError, match="sheet 'Totals'") as exc_info:
        run_module._extract_historical_series_headers_by_sheet(Path("unused.xlsx"))

    assert "loading historical worksheet" in str(exc_info.value)
    assert "unused.xlsx" in str(exc_info.value)
    assert workbook.closed is True
