"""Historical workbook validation coverage for pipeline workbook append behavior."""

from __future__ import annotations

import sys
import types
from datetime import date
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
    def __init__(self, sheets: dict[str, _FakeWorksheet]) -> None:
        self._sheets = dict(sheets)
        self.sheetnames = list(sheets)
        self.saved_paths: list[Path] = []
        self.closed = False

    def __getitem__(self, item: str) -> _FakeWorksheet:
        return self._sheets[item]

    def save(self, path: Path) -> None:
        self.saved_paths.append(path)
        path.write_bytes(b"updated")

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def workbook_path(tmp_path: Path) -> Path:
    path = tmp_path / "historical.xlsx"
    path.write_bytes(b"initial")
    return path


def _base_target_sheet(*, first_header: str | None, second_header: str | None) -> _FakeWorksheet:
    target = _FakeWorksheet("Total")
    target.set_value(1, 1, "Date")
    target.set_value(1, 2, first_header)
    target.set_value(1, 3, second_header)
    target.set_value(2, 1, "2025-12-31")
    return target


def test_historical_validation_missing_header_includes_sheet_and_missing_columns(
    workbook_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workbook = _FakeWorkbook(
        {"Total": _base_target_sheet(first_header=None, second_header="Series B")}
    )
    monkeypatch.setattr(
        "counter_risk.pipeline.run._PREFERRED_HISTORICAL_SHEET_BY_VARIANT",
        {"all_programs": "Total"},
    )
    monkeypatch.setitem(
        sys.modules, "openpyxl", types.SimpleNamespace(load_workbook=lambda filename: workbook)
    )

    with pytest.raises(RuntimeError, match="Failed to update historical workbook") as exc_info:
        run_module._merge_historical_workbook(
            workbook_path=workbook_path,
            variant="all_programs",
            as_of_date=date(2026, 2, 13),
            totals_records=[{"Notional": 10.0, "counterparty": "A"}],
            warnings=[],
        )

    cause_message = str(exc_info.value.__cause__)
    assert "Total" in cause_message
    assert "missing required columns" in cause_message
    assert "value series 1" in cause_message
    assert workbook.saved_paths == []


def test_historical_validation_with_decoy_and_target_sheet_appends_only_to_target(
    workbook_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decoy = _FakeWorksheet("A Decoy")
    decoy.set_value(1, 1, "Date")
    decoy.set_value(1, 2, "Wrong")
    decoy.set_value(1, 3, "Wrong")
    decoy.set_value(2, 1, "2025-12-31")

    target = _base_target_sheet(first_header="Series A", second_header="Series B")

    workbook = _FakeWorkbook({"A Decoy": decoy, "Total": target})
    monkeypatch.setitem(
        sys.modules, "openpyxl", types.SimpleNamespace(load_workbook=lambda filename: workbook)
    )

    run_module._merge_historical_workbook(
        workbook_path=workbook_path,
        variant="all_programs",
        as_of_date=date(2026, 2, 13),
        totals_records=[
            {"Notional": 20.0, "counterparty": "A"},
            {"Notional": 5.0, "counterparty": "B"},
        ],
        warnings=[],
    )

    assert target.cell(row=3, column=1).value == "2026-02-13"
    assert target.cell(row=3, column=2).value == pytest.approx(25.0)
    assert target.cell(row=3, column=3).value == 2
    assert decoy.cell(row=3, column=1).value is None


def test_historical_validation_valid_workbook_updates_copy_under_run_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx"
    source_path.write_bytes(b"source")

    run_dir = tmp_path / "runs" / "2026-02-13"
    run_dir.mkdir(parents=True)
    run_copy_path = run_dir / source_path.name
    run_copy_path.write_bytes(source_path.read_bytes())

    target = _base_target_sheet(first_header="Series A", second_header="Series B")
    workbook = _FakeWorkbook({"Total": target})
    monkeypatch.setitem(
        sys.modules, "openpyxl", types.SimpleNamespace(load_workbook=lambda filename: workbook)
    )

    run_module._merge_historical_workbook(
        workbook_path=run_copy_path,
        variant="all_programs",
        as_of_date=date(2026, 2, 13),
        totals_records=[
            {"Notional": 30.0, "counterparty": "A"},
            {"Notional": 12.0, "counterparty": "B"},
            {"Notional": 3.0, "counterparty": "B"},
        ],
        warnings=[],
    )

    assert source_path.read_bytes() == b"source"
    assert run_copy_path.read_bytes() == b"updated"
    assert target.cell(row=3, column=1).value == "2026-02-13"
    assert target.cell(row=3, column=2).value == pytest.approx(45.0)
    assert target.cell(row=3, column=3).value == 2
