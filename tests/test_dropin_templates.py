"""Tests for drop-in template writer scaffolding."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from counter_risk.writers.dropin_templates import _build_exposure_index, fill_dropin_template


def test_fill_dropin_template_raises_for_missing_template(tmp_path: Path) -> None:
    missing = tmp_path / "missing-template.xlsx"

    with pytest.raises(FileNotFoundError):
        fill_dropin_template(
            template_path=missing,
            exposures_df=[],
            breakdown={},
            output_path=tmp_path / "out.xlsx",
        )


def test_fill_dropin_template_validates_exposures_type(tmp_path: Path) -> None:
    fake_template = tmp_path / "template.xlsx"
    fake_template.write_text("placeholder", encoding="utf-8")

    with pytest.raises(TypeError, match="exposures_df"):
        fill_dropin_template(
            template_path=fake_template,
            exposures_df=42,
            breakdown={},
            output_path=tmp_path / "out.xlsx",
        )


def test_build_exposure_index_normalizes_counterparty_and_clearing_house_labels() -> None:
    rows: list[dict[str, Any]] = [
        {"counterparty": "  Societe   Generale "},
        {"clearing_house": " ICE   Clear   U.S. "},
    ]

    indexed = _build_exposure_index(rows)

    assert "soc gen" in indexed
    assert "ice" in indexed


def test_fill_dropin_template_validates_non_empty_path_arguments(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="template_path"):
        fill_dropin_template(
            template_path="",
            exposures_df=[],
            breakdown={},
            output_path=tmp_path / "out.xlsx",
        )


def test_fill_dropin_template_validates_output_suffix(tmp_path: Path) -> None:
    fake_template = tmp_path / "template.xlsx"
    fake_template.write_text("placeholder", encoding="utf-8")

    with pytest.raises(ValueError, match="output_path"):
        fill_dropin_template(
            template_path=fake_template,
            exposures_df=[],
            breakdown={},
            output_path=tmp_path / "out.xls",
        )


def test_fill_dropin_template_rejects_directory_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="template_path"):
        fill_dropin_template(
            template_path=tmp_path,
            exposures_df=[],
            breakdown={},
            output_path=tmp_path / "out.xlsx",
        )


def test_fill_dropin_template_validates_template_suffix(tmp_path: Path) -> None:
    fake_template = tmp_path / "template.xls"
    fake_template.write_text("placeholder", encoding="utf-8")

    with pytest.raises(ValueError, match=r"\.xlsx"):
        fill_dropin_template(
            template_path=fake_template,
            exposures_df=[],
            breakdown={},
            output_path=tmp_path / "out.xlsx",
        )


def test_fill_dropin_template_validates_breakdown_mapping(tmp_path: Path) -> None:
    fake_template = tmp_path / "template.xlsx"
    fake_template.write_text("placeholder", encoding="utf-8")

    with pytest.raises(TypeError, match="breakdown"):
        fill_dropin_template(
            template_path=fake_template,
            exposures_df=[],
            breakdown=[],  # type: ignore[arg-type]
            output_path=tmp_path / "out.xlsx",
        )


def test_fill_dropin_template_validates_breakdown_value_type(tmp_path: Path) -> None:
    fake_template = tmp_path / "template.xlsx"
    fake_template.write_text("placeholder", encoding="utf-8")

    with pytest.raises(ValueError, match="must be numeric"):
        fill_dropin_template(
            template_path=fake_template,
            exposures_df=[],
            breakdown={"total": "not-a-number"},
            output_path=tmp_path / "out.xlsx",
        )


def test_fill_dropin_template_validates_iterable_rows_are_mappings(tmp_path: Path) -> None:
    fake_template = tmp_path / "template.xlsx"
    fake_template.write_text("placeholder", encoding="utf-8")

    with pytest.raises(TypeError, match="row at index 0"):
        fill_dropin_template(
            template_path=fake_template,
            exposures_df=[1],
            breakdown={},
            output_path=tmp_path / "out.xlsx",
        )


class _FakeCell:
    def __init__(self, row: int, column: int, value: Any = None) -> None:
        self.row = row
        self.column = column
        self.value = value


class _FakeWorksheet:
    def __init__(self, rows: int = 40, cols: int = 20) -> None:
        self.max_row = rows
        self.max_column = cols
        self._cells: dict[tuple[int, int], _FakeCell] = {}

    def cell(self, row: int, column: int) -> _FakeCell:
        key = (row, column)
        if key not in self._cells:
            self._cells[key] = _FakeCell(row=row, column=column, value=None)
        return self._cells[key]

    def set_value(self, row: int, column: int, value: Any) -> None:
        self.cell(row=row, column=column).value = value

    def iter_rows(
        self,
        *,
        min_row: int,
        max_row: int,
        min_col: int,
        max_col: int,
    ) -> list[list[_FakeCell]]:
        return [
            [self.cell(row=row, column=col) for col in range(min_col, max_col + 1)]
            for row in range(min_row, max_row + 1)
        ]


class _FakeWorkbook:
    def __init__(self, worksheet: _FakeWorksheet) -> None:
        self.active = worksheet
        self.saved_path: Path | None = None
        self.closed = False

    def save(self, path: Path) -> None:
        self.saved_path = path

    def close(self) -> None:
        self.closed = True


def _install_fake_openpyxl(monkeypatch: pytest.MonkeyPatch, workbook: _FakeWorkbook) -> None:
    fake_module = ModuleType("openpyxl")
    fake_module.load_workbook = lambda filename: workbook  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openpyxl", fake_module)


def test_fill_dropin_template_populates_asset_and_notional_cells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_template = tmp_path / "template.xlsx"
    fake_template.write_text("placeholder", encoding="utf-8")

    sheet = _FakeWorksheet()
    sheet.set_value(5, 2, "Counterparty/ \nClearing House")
    sheet.set_value(6, 4, "TIPS")
    sheet.set_value(6, 5, "Treasury")
    sheet.set_value(6, 6, "Equity")
    sheet.set_value(6, 7, "Commodity")
    sheet.set_value(6, 8, "Currency")
    sheet.set_value(6, 10, "Notional")
    sheet.set_value(6, 11, "from prior month")
    sheet.set_value(8, 2, "Societe Generale")

    workbook = _FakeWorkbook(sheet)
    _install_fake_openpyxl(monkeypatch, workbook)

    output = fill_dropin_template(
        template_path=fake_template,
        exposures_df=[
            {
                "counterparty": "Societe Generale",
                "tips": 10,
                "treasury": 11,
                "equity": 12,
                "commodity": 13,
                "currency": 14,
                "notional": 60,
                "notional_change": -2,
            }
        ],
        breakdown={},
        output_path=tmp_path / "out.xlsx",
    )

    assert output == tmp_path / "out.xlsx"
    assert workbook.saved_path == tmp_path / "out.xlsx"
    assert workbook.closed is True
    assert sheet.cell(8, 4).value == 10.0
    assert sheet.cell(8, 5).value == 11.0
    assert sheet.cell(8, 6).value == 12.0
    assert sheet.cell(8, 7).value == 13.0
    assert sheet.cell(8, 8).value == 14.0
    assert sheet.cell(8, 10).value == 60.0
    assert sheet.cell(8, 11).value == -2.0


def test_fill_dropin_template_rejects_non_numeric_values_for_template_cells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_template = tmp_path / "template.xlsx"
    fake_template.write_text("placeholder", encoding="utf-8")

    sheet = _FakeWorksheet()
    sheet.set_value(5, 2, "Counterparty/ \nClearing House")
    sheet.set_value(6, 6, "Equity")
    sheet.set_value(8, 2, "Societe Generale")

    workbook = _FakeWorkbook(sheet)
    _install_fake_openpyxl(monkeypatch, workbook)

    with pytest.raises(ValueError, match="must be numeric"):
        fill_dropin_template(
            template_path=fake_template,
            exposures_df=[{"counterparty": "Societe Generale", "equity": "abc"}],
            breakdown={},
            output_path=tmp_path / "out.xlsx",
        )
