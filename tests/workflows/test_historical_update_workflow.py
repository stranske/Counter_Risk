"""Tests for WAL historical update workflow CLI wiring."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from counter_risk.workflows import historical_update


def test_main_parses_date_and_calls_calculate_then_append_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exposure_summary_path = tmp_path / "exposure-summary.xlsx"
    exposure_summary_path.write_text("placeholder", encoding="utf-8")
    workbook_path = tmp_path / "historical.xlsx"
    workbook_path.write_text("placeholder", encoding="utf-8")

    calls: list[tuple[str, object, object]] = []

    def _fake_locate() -> Path:
        return workbook_path

    def _fake_calculate(path: Path, px_date: date) -> float:
        calls.append(("calculate_wal", path, px_date))
        return 3.14159

    def _fake_append(path: Path, *, px_date: date, wal_value: float) -> Path:
        calls.append(("append_wal_row", path, (px_date, wal_value)))
        return path

    monkeypatch.setattr(historical_update, "locate_ex_llc_3_year_workbook", _fake_locate)
    monkeypatch.setattr(historical_update, "calculate_wal", _fake_calculate)
    monkeypatch.setattr(historical_update, "append_wal_row", _fake_append)

    exit_code = historical_update.main(
        [
            "--date",
            "2026-01-31",
            "--exposure-summary-path",
            str(exposure_summary_path),
        ]
    )

    assert exit_code == 0
    assert calls == [
        ("calculate_wal", exposure_summary_path, date(2026, 1, 31)),
        ("append_wal_row", workbook_path, (date(2026, 1, 31), 3.14159)),
    ]
