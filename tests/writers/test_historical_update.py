"""Boundary regressions for historical WAL workbook persistence."""

from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

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
