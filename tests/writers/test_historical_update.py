"""Boundary regressions for historical workbook persistence."""

from collections.abc import Callable
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

from counter_risk.writers import historical_update
from counter_risk.writers.historical_update import append_wal_row


@pytest.fixture
def wal_workbook(tmp_path: Path) -> Path:
    openpyxl = pytest.importorskip("openpyxl")
    path = tmp_path / "historical.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "WAL"
    sheet.append(["Date", "WAL TIPS REPO"])
    sheet.append([date(2026, 1, 31), 2.25])
    workbook.save(path)
    workbook.close()
    return path


@pytest.mark.parametrize(
    "wal_value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        -1.0,
        -1e-300,
        "nan",
        "inf",
        "-inf",
        "1e999",
        "-0.5",
        10**400,
        None,
        "invalid",
    ],
    ids=[
        "nan",
        "inf",
        "negative-inf",
        "negative",
        "tiny-negative",
        "nan-string",
        "inf-string",
        "negative-inf-string",
        "overflow-string",
        "negative-string",
        "overflow-int",
        "none",
        "nonnumeric",
    ],
)
def test_append_wal_row_rejects_invalid_value_before_workbook_io(
    wal_workbook: Path, monkeypatch: pytest.MonkeyPatch, wal_value: object
) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    original_bytes = wal_workbook.read_bytes()
    loader = Mock(wraps=openpyxl.load_workbook)
    monkeypatch.setattr(openpyxl, "load_workbook", loader)

    with pytest.raises(ValueError, match="wal_value must be finite and non-negative"):
        append_wal_row(wal_workbook, px_date=date(2026, 2, 28), wal_value=wal_value)

    loader.assert_not_called()
    assert wal_workbook.read_bytes() == original_bytes


@pytest.mark.parametrize("wal_value", [0.0, 2.35, "0.0", "2.35"])
def test_append_wal_row_persists_valid_value(wal_workbook: Path, wal_value: float | str) -> None:
    openpyxl = pytest.importorskip("openpyxl")

    result = append_wal_row(wal_workbook, px_date=date(2026, 2, 28), wal_value=wal_value)

    assert result == wal_workbook
    workbook = openpyxl.load_workbook(wal_workbook)
    try:
        sheet = workbook["WAL"]
        assert sheet.max_row == 3
        assert sheet.cell(2, 2).value == 2.25
        assert sheet.cell(3, 1).value.date() == date(2026, 2, 28)
        assert sheet.cell(3, 2).value == pytest.approx(float(wal_value))
    finally:
        workbook.close()


NONFINITE_ROLLUPS = [
    pytest.param(float("nan"), id="nan"),
    pytest.param(float("inf"), id="inf"),
    pytest.param(float("-inf"), id="negative-inf"),
    pytest.param("NaN", id="nan-string"),
    pytest.param("Infinity", id="infinity-string"),
    pytest.param("-Infinity", id="negative-infinity-string"),
    pytest.param("1e999", id="overflow-string"),
    pytest.param("-1e999", id="negative-overflow-string"),
]
HISTORICAL_APPENDERS = [
    pytest.param(
        historical_update.SHEET_ALL_PROGRAMS_3_YEAR,
        historical_update.append_row_all_programs,
        id="all-programs",
    ),
    pytest.param(
        historical_update.SHEET_EX_LLC_3_YEAR,
        historical_update.append_row_ex_trend,
        id="ex-llc",
    ),
    pytest.param(
        historical_update.SHEET_LLC_3_YEAR,
        historical_update.append_row_trend,
        id="llc",
    ),
]


@pytest.mark.parametrize("value", NONFINITE_ROLLUPS)
def test_coerce_rollup_data_rejects_nonfinite_values(value: object) -> None:
    with pytest.raises(historical_update.HistoricalUpdateError, match="'Total' must be finite"):
        historical_update._coerce_rollup_data({"Cash": 25.0, "Total": value})


@pytest.mark.parametrize("value", [None, "invalid", 10**400])
def test_coerce_rollup_data_wraps_conversion_errors(value: object) -> None:
    with pytest.raises(historical_update.HistoricalUpdateError, match="'Total' must be numeric"):
        historical_update._coerce_rollup_data({"Total": value})


@pytest.mark.parametrize("value", [0.0, -12.5, 1e308, "-12.5"])
def test_coerce_rollup_data_preserves_finite_values(value: float | str) -> None:
    assert historical_update._coerce_rollup_data({"Total": value}) == {"total": float(value)}


@pytest.fixture
def rollup_workbook(tmp_path: Path) -> Path:
    openpyxl = pytest.importorskip("openpyxl")
    path = tmp_path / "historical-rollups.xlsx"
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for sheet_name in historical_update.SERIES_BY_SHEET:
        sheet = workbook.create_sheet(sheet_name)
        sheet.append(["Date", "Total", "Cash"])
        sheet.append([date(2026, 1, 31), 100.0, "=B2/4"])
        sheet.cell(2, 2).number_format = "0.00"
    workbook.save(path)
    workbook.close()
    return path


@pytest.mark.parametrize("sheet_name,append_row", HISTORICAL_APPENDERS)
@pytest.mark.parametrize("value", NONFINITE_ROLLUPS)
def test_append_historical_row_rejects_nonfinite_without_modifying_workbook(
    rollup_workbook: Path,
    monkeypatch: pytest.MonkeyPatch,
    sheet_name: str,
    append_row,
    value: object,
) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    original_bytes = rollup_workbook.read_bytes()
    workbook = openpyxl.load_workbook(rollup_workbook)
    original_sheets = {
        sheet.title: [
            [(cell.value, cell.number_format) for cell in row] for row in sheet.iter_rows()
        ]
        for sheet in workbook
    }
    save = Mock(wraps=workbook.save)
    monkeypatch.setattr(workbook, "save", save)
    monkeypatch.setattr(openpyxl, "load_workbook", Mock(return_value=workbook))

    with pytest.raises(historical_update.HistoricalUpdateError, match="'Total' must be finite"):
        append_row(
            rollup_workbook,
            {"Cash": 25.0, "Total": value},
            append_date=date(2026, 2, 28),
        )

    save.assert_not_called()
    assert rollup_workbook.read_bytes() == original_bytes
    assert workbook[sheet_name].max_row == 2
    assert {
        sheet.title: [
            [(cell.value, cell.number_format) for cell in row] for row in sheet.iter_rows()
        ]
        for sheet in workbook
    } == original_sheets


@pytest.mark.parametrize("sheet_name,append_row", HISTORICAL_APPENDERS)
def test_append_historical_row_persists_finite_rollups(
    rollup_workbook: Path, sheet_name: str, append_row: Callable[..., Path]
) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    result = append_row(
        rollup_workbook,
        {"Total": "-12.5", "Cash": 0.0},
        append_date=date(2026, 2, 28),
    )
    assert result == rollup_workbook
    workbook = openpyxl.load_workbook(rollup_workbook)
    try:
        sheet = workbook[sheet_name]
        assert sheet.cell(3, 1).value.date() == date(2026, 2, 28)
        assert sheet.cell(3, 2).value == -12.5
        assert sheet.cell(3, 3).value == 0.0
        assert sheet.cell(2, 3).value == "=B2/4"
        for other_sheet in workbook:
            if other_sheet.title != sheet_name:
                assert other_sheet.max_row == 2
    finally:
        workbook.close()
