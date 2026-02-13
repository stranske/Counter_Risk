"""Tests for drop-in template writer scaffolding."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from counter_risk.writers.dropin_templates import (
    _TEMPLATE_HEADER_LABEL_TO_METRIC,
    _build_exposure_index,
    _normalize_header_label,
    fill_dropin_template,
)


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


def test_fill_dropin_template_validates_counterparty_identifier_columns(tmp_path: Path) -> None:
    fake_template = tmp_path / "template.xlsx"
    fake_template.write_text("placeholder", encoding="utf-8")

    with pytest.raises(ValueError, match="counterparty identifier"):
        fill_dropin_template(
            template_path=fake_template,
            exposures_df=[{"tips": 10, "notional": 10}],
            breakdown={},
            output_path=tmp_path / "out.xlsx",
        )


def test_fill_dropin_template_validates_non_empty_counterparty_identifier_values(
    tmp_path: Path,
) -> None:
    fake_template = tmp_path / "template.xlsx"
    fake_template.write_text("placeholder", encoding="utf-8")

    with pytest.raises(ValueError, match="counterparty identifier"):
        fill_dropin_template(
            template_path=fake_template,
            exposures_df=[{"counterparty": "   ", "tips": 10, "notional": 10}],
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


def test_fill_dropin_template_loads_template_via_openpyxl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_template = tmp_path / "template.xlsx"
    fake_template.write_text("placeholder", encoding="utf-8")
    workbook = _FakeWorkbook(_FakeWorksheet())
    captured_filename: dict[str, Any] = {}

    fake_module = ModuleType("openpyxl")

    def _load_workbook(filename: Path) -> _FakeWorkbook:
        captured_filename["value"] = filename
        return workbook

    fake_module.load_workbook = _load_workbook  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openpyxl", fake_module)

    fill_dropin_template(
        template_path=fake_template,
        exposures_df=[],
        breakdown={},
        output_path=tmp_path / "out.xlsx",
    )

    assert captured_filename["value"] == fake_template


def test_fill_dropin_template_raises_for_unloadable_workbook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_template = tmp_path / "template.xlsx"
    fake_template.write_text("placeholder", encoding="utf-8")

    fake_module = ModuleType("openpyxl")

    def _load_workbook(filename: Path) -> _FakeWorkbook:
        msg = f"cannot open {filename}"
        raise OSError(msg)

    fake_module.load_workbook = _load_workbook  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openpyxl", fake_module)

    with pytest.raises(ValueError, match="Unable to load template workbook"):
        fill_dropin_template(
            template_path=fake_template,
            exposures_df=[],
            breakdown={},
            output_path=tmp_path / "out.xlsx",
        )


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


def test_fill_dropin_template_populates_notional_breakdown_row(
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
    sheet.set_value(12, 2, "Notional Breakdown")

    workbook = _FakeWorkbook(sheet)
    _install_fake_openpyxl(monkeypatch, workbook)

    fill_dropin_template(
        template_path=fake_template,
        exposures_df=[],
        breakdown={
            "tips": 0.11,
            "treasury": 0.22,
            "equity": 0.33,
            "commodity": 0.44,
            "currency": 0.55,
            "notional": 1.0,
        },
        output_path=tmp_path / "out.xlsx",
    )

    assert sheet.cell(12, 4).value == pytest.approx(0.11)
    assert sheet.cell(12, 5).value == pytest.approx(0.22)
    assert sheet.cell(12, 6).value == pytest.approx(0.33)
    assert sheet.cell(12, 7).value == pytest.approx(0.44)
    assert sheet.cell(12, 8).value == pytest.approx(0.55)
    assert sheet.cell(12, 10).value == pytest.approx(1.0)


def _find_row_by_label(worksheet: Any, label: str, *, column: int = 2) -> int:
    for row_index in range(1, int(getattr(worksheet, "max_row", 0)) + 1):
        value = worksheet.cell(row=row_index, column=column).value
        if isinstance(value, str) and value.strip() == label:
            return row_index
    raise AssertionError(f"Unable to find row label {label!r} in column {column}")


def _find_metric_columns(worksheet: Any) -> dict[str, int]:
    columns: dict[str, int] = {}
    for row in worksheet.iter_rows(min_row=1, max_row=20, min_col=1, max_col=30):
        for cell in row:
            if not isinstance(cell.value, str):
                continue
            metric = _TEMPLATE_HEADER_LABEL_TO_METRIC.get(_normalize_header_label(cell.value))
            if metric is not None:
                columns[metric] = int(cell.column)
    return columns


def test_fill_dropin_template_populates_all_programs_fixture_counterparty_rows(
    tmp_path: Path,
) -> None:
    openpyxl = pytest.importorskip("openpyxl")

    template = Path("tests/fixtures/NISA Drop-In Template - All Programs.xlsx")
    output = tmp_path / "all-programs-output.xlsx"

    exposures = [
        {
            "counterparty": "Citigroup",
            "cash": 100,
            "tips": 110,
            "treasury": 120,
            "equity": 130,
            "commodity": 140,
            "currency": 150,
            "notional": 750,
            "notional_change": 50,
        },
        {
            "counterparty": "Bank of America, NA",
            "cash": 200,
            "tips": 210,
            "treasury": 220,
            "equity": 230,
            "commodity": 240,
            "currency": 250,
            "notional": 1350,
            "notional_change": -5,
        },
        {
            "counterparty": "Goldman Sachs Int'l",
            "cash": 300,
            "tips": 310,
            "treasury": 320,
            "equity": 330,
            "commodity": 340,
            "currency": 350,
            "notional": 1950,
            "notional_change": 0,
        },
        {
            "counterparty": "JP Morgan",
            "cash": 400,
            "tips": 410,
            "treasury": 420,
            "equity": 430,
            "commodity": 440,
            "currency": 450,
            "notional": 2550,
            "notional_change": 15,
        },
        {
            "counterparty": "Societe Generale",
            "cash": 500,
            "tips": 510,
            "treasury": 520,
            "equity": 530,
            "commodity": 540,
            "currency": 550,
            "notional": 3150,
            "notional_change": -25,
        },
    ]

    fill_dropin_template(
        template_path=template,
        exposures_df=exposures,
        breakdown={"notional": 1},
        output_path=output,
    )

    workbook = openpyxl.load_workbook(output, data_only=True)
    worksheet = workbook.active
    metric_columns = _find_metric_columns(worksheet)

    expected_notional = {
        "Citigroup": 750.0,
        "Bank of America, NA": 1350.0,
        "Goldman Sachs Int'l": 1950.0,
        "JP Morgan": 2550.0,
        "Societe Generale": 3150.0,
    }
    for counterparty, expected_value in expected_notional.items():
        row = _find_row_by_label(worksheet, counterparty)
        assert worksheet.cell(row=row, column=metric_columns["notional"]).value == expected_value

    workbook.close()


def test_fill_dropin_template_populates_ex_trend_fixture_numeric_cells(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")

    template = Path("tests/fixtures/NISA Drop-In Template - Ex Trend.xlsx")
    output = tmp_path / "ex-trend-output.xlsx"

    exposures = [
        {
            "counterparty": "Citigroup",
            "tips": 1001,
            "treasury": 1002,
            "equity": 1003,
            "commodity": 1004,
            "currency": 1005,
            "notional": 5015,
            "notional_change": 15,
        },
        {
            "counterparty": "Bank of America, NA",
            "tips": 2001,
            "treasury": 2002,
            "equity": 2003,
            "commodity": 2004,
            "currency": 2005,
            "notional": 10015,
            "notional_change": -35,
        },
        {
            "counterparty": "Goldman Sachs Int'l",
            "tips": 3001,
            "treasury": 3002,
            "equity": 3003,
            "commodity": 3004,
            "currency": 3005,
            "notional": 15015,
            "notional_change": 60,
        },
        {
            "counterparty": "JP Morgan",
            "tips": 4001,
            "treasury": 4002,
            "equity": 4003,
            "commodity": 4004,
            "currency": 4005,
            "notional": 20015,
            "notional_change": -80,
        },
        {
            "counterparty": "Societe Generale",
            "tips": 5001,
            "treasury": 5002,
            "equity": 5003,
            "commodity": 5004,
            "currency": 5005,
            "notional": 25015,
            "notional_change": 95,
        },
    ]

    fill_dropin_template(
        template_path=template,
        exposures_df=exposures,
        breakdown={"notional": 1},
        output_path=output,
    )

    workbook = openpyxl.load_workbook(output, data_only=True)
    worksheet = workbook.active
    metric_columns = _find_metric_columns(worksheet)

    expected_notional_change = {
        "Citigroup": 15.0,
        "Bank of America, NA": -35.0,
        "Goldman Sachs Int'l": 60.0,
        "JP Morgan": -80.0,
        "Societe Generale": 95.0,
    }
    for counterparty, expected_value in expected_notional_change.items():
        row = _find_row_by_label(worksheet, counterparty)
        assert (
            worksheet.cell(row=row, column=metric_columns["notional_change"]).value
            == expected_value
        )

    workbook.close()


def test_fill_dropin_template_populates_trend_fixture_notional_breakdown_row(
    tmp_path: Path,
) -> None:
    openpyxl = pytest.importorskip("openpyxl")

    template = Path("tests/fixtures/NISA Drop-In Template - Trend.xlsx")
    output = tmp_path / "trend-output.xlsx"

    exposures = [
        {
            "counterparty": "CME",
            "tips": 10,
            "treasury": 20,
            "equity": 30,
            "commodity": 40,
            "currency": 50,
            "notional": 150,
            "notional_change": 1,
        },
        {
            "counterparty": "EUREX",
            "tips": 11,
            "treasury": 21,
            "equity": 31,
            "commodity": 41,
            "currency": 51,
            "notional": 155,
            "notional_change": 2,
        },
        {
            "counterparty": "ICE Euro",
            "tips": 12,
            "treasury": 22,
            "equity": 32,
            "commodity": 42,
            "currency": 52,
            "notional": 160,
            "notional_change": 3,
        },
        {
            "counterparty": "ICE",
            "tips": 13,
            "treasury": 23,
            "equity": 33,
            "commodity": 43,
            "currency": 53,
            "notional": 165,
            "notional_change": 4,
        },
        {
            "counterparty": "Japan SCC",
            "tips": 14,
            "treasury": 24,
            "equity": 34,
            "commodity": 44,
            "currency": 54,
            "notional": 170,
            "notional_change": 5,
        },
    ]
    breakdown = {
        "tips": 0.40,
        "treasury": 0.30,
        "equity": 0.20,
        "commodity": 0.10,
        "currency": 0.00,
        "notional": 1.00,
    }

    fill_dropin_template(
        template_path=template,
        exposures_df=exposures,
        breakdown=breakdown,
        output_path=output,
    )

    workbook = openpyxl.load_workbook(output, data_only=True)
    worksheet = workbook.active
    metric_columns = _find_metric_columns(worksheet)
    breakdown_row = _find_row_by_label(worksheet, "Notional Breakdown")
    expected_notional = {
        "CME": 150.0,
        "EUREX": 155.0,
        "ICE Euro": 160.0,
        "ICE": 165.0,
        "Japan SCC": 170.0,
    }

    for counterparty, expected_value in expected_notional.items():
        row = _find_row_by_label(worksheet, counterparty)
        assert worksheet.cell(row=row, column=metric_columns["notional"]).value == expected_value

    assert worksheet.cell(row=breakdown_row, column=metric_columns["tips"]).value == pytest.approx(
        0.40
    )
    assert worksheet.cell(
        row=breakdown_row, column=metric_columns["treasury"]
    ).value == pytest.approx(0.30)
    assert worksheet.cell(
        row=breakdown_row, column=metric_columns["equity"]
    ).value == pytest.approx(0.20)
    assert worksheet.cell(
        row=breakdown_row, column=metric_columns["commodity"]
    ).value == pytest.approx(0.10)
    assert worksheet.cell(
        row=breakdown_row, column=metric_columns["notional"]
    ).value == pytest.approx(1.00)

    workbook.close()


def test_fill_dropin_template_generated_workbooks_reopen_cleanly_for_all_variants(
    tmp_path: Path,
) -> None:
    openpyxl = pytest.importorskip("openpyxl")

    cases = [
        (
            Path("tests/fixtures/NISA Drop-In Template - All Programs.xlsx"),
            tmp_path / "all-programs-reopen.xlsx",
            [
                {"counterparty": "Citigroup", "notional": 1},
                {"counterparty": "Bank of America, NA", "notional": 2},
                {"counterparty": "Goldman Sachs Int'l", "notional": 3},
                {"counterparty": "JP Morgan", "notional": 4},
                {"counterparty": "Societe Generale", "notional": 5},
            ],
        ),
        (
            Path("tests/fixtures/NISA Drop-In Template - Ex Trend.xlsx"),
            tmp_path / "ex-trend-reopen.xlsx",
            [
                {"counterparty": "Citigroup", "notional": 11},
                {"counterparty": "Bank of America, NA", "notional": 12},
                {"counterparty": "Goldman Sachs Int'l", "notional": 13},
                {"counterparty": "JP Morgan", "notional": 14},
                {"counterparty": "Societe Generale", "notional": 15},
            ],
        ),
        (
            Path("tests/fixtures/NISA Drop-In Template - Trend.xlsx"),
            tmp_path / "trend-reopen.xlsx",
            [
                {"counterparty": "CME", "notional": 21},
                {"counterparty": "EUREX", "notional": 22},
                {"counterparty": "ICE Euro", "notional": 23},
                {"counterparty": "ICE", "notional": 24},
                {"counterparty": "Japan SCC", "notional": 25},
            ],
        ),
    ]

    for template, output, exposures in cases:
        fill_dropin_template(
            template_path=template,
            exposures_df=exposures,
            breakdown={"notional": 1.0},
            output_path=output,
        )

        workbook = openpyxl.load_workbook(output, data_only=True)
        assert workbook.active.max_row > 0
        workbook.close()


def test_fill_dropin_template_rejects_malformed_template_file(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    assert openpyxl is not None

    malformed_template = tmp_path / "malformed.xlsx"
    malformed_template.write_bytes(b"not-a-valid-xlsx")

    with pytest.raises(ValueError, match="Unable to load template workbook"):
        fill_dropin_template(
            template_path=malformed_template,
            exposures_df=[],
            breakdown={},
            output_path=tmp_path / "out.xlsx",
        )
