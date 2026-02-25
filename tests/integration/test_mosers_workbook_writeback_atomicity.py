from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.io.mosers_workbook import (
    FuturesDetailNotFoundError,
    atomic_writeback_with_section_locate,
)


def _build_source_without_futures_detail(path: Path) -> Path:
    from openpyxl import Workbook  # type: ignore[import-untyped]

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Inputs"
    worksheet["A1"] = "Not the expected marker"
    worksheet["A2"] = "Description"
    worksheet["B2"] = "Prior Month Notional"
    worksheet["A3"] = "TY Mar25"
    worksheet["B3"] = 123.0
    workbook.save(path)
    workbook.close()
    return path


def test_atomic_writeback_aborts_without_creating_output_when_section_locate_fails(
    tmp_path: Path,
) -> None:
    source_path = _build_source_without_futures_detail(tmp_path / "source.xlsx")
    output_path = tmp_path / "output.xlsx"

    with pytest.raises(FuturesDetailNotFoundError):
        atomic_writeback_with_section_locate(
            source_path=source_path,
            output_path=output_path,
            rows=[{"description": "TY Mar25", "prior_notional": 77.0}],
        )

    assert not output_path.exists()


def test_atomic_writeback_removes_temp_files_when_section_locate_fails(tmp_path: Path) -> None:
    source_path = _build_source_without_futures_detail(tmp_path / "source.xlsx")
    output_path = tmp_path / "output.xlsx"

    with pytest.raises(FuturesDetailNotFoundError):
        atomic_writeback_with_section_locate(
            source_path=source_path,
            output_path=output_path,
            rows=[{"description": "TY Mar25", "prior_notional": 77.0}],
        )

    assert list(tmp_path.glob("*.tmp.xlsx")) == []
    assert list(tmp_path.glob("~$*")) == []
