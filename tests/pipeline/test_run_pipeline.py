"""Integration-style tests for pipeline orchestration."""

from __future__ import annotations

import hashlib
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from counter_risk.pipeline.run import run_pipeline


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

    def to_dict(self, orient: str = "records") -> list[dict[str, Any]]:
        if orient != "records":
            raise ValueError("Only orient='records' is supported")
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def test_run_pipeline_writes_expected_outputs_and_manifest(tmp_path: Path, fake_pandas: None) -> None:
    fixtures = Path("tests/fixtures")
    output_root = tmp_path / "runs"

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "\n".join(
            [
                "as_of_date: 2025-12-31",
                f"mosers_all_programs_xlsx: {fixtures / 'MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx'}",
                f"mosers_ex_trend_xlsx: {fixtures / 'MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx'}",
                f"mosers_trend_xlsx: {fixtures / 'MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx'}",
                f"hist_all_programs_3yr_xlsx: {fixtures / 'Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx'}",
                f"hist_ex_llc_3yr_xlsx: {fixtures / 'Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx'}",
                f"hist_llc_3yr_xlsx: {fixtures / 'Historical Counterparty Risk Graphs - LLC 3 Year.xlsx'}",
                f"monthly_pptx: {fixtures / 'Monthly Counterparty Exposure Report.pptx'}",
                f"output_root: {output_root}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    run_dir = run_pipeline(config_path)

    assert run_dir == output_root / "2025-12-31"
    assert run_dir.exists()

    manifest_path = run_dir / "manifest.json"
    assert manifest_path.exists()

    expected_outputs = [
        run_dir / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx",
        run_dir / "Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx",
        run_dir / "Historical Counterparty Risk Graphs - LLC 3 Year.xlsx",
        run_dir / "all_programs-mosers-input.xlsx",
        run_dir / "ex_trend-mosers-input.xlsx",
        run_dir / "trend-mosers-input.xlsx",
        run_dir / "Monthly Counterparty Exposure Report.pptx",
    ]
    for output_file in expected_outputs:
        assert output_file.exists(), f"Missing output file: {output_file}"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["as_of_date"] == "2025-12-31"
    assert manifest["config_snapshot"]["output_root"] == str(output_root)

    for output_path in manifest["output_paths"]:
        assert Path(output_path).exists(), f"Manifest references missing path: {output_path}"

    assert "PPT links not refreshed; COM refresh skipped" in manifest["warnings"]

    expected_hashes = {
        "mosers_all_programs_xlsx": _sha256(
            fixtures / "MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx"
        ),
        "mosers_ex_trend_xlsx": _sha256(
            fixtures / "MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx"
        ),
        "mosers_trend_xlsx": _sha256(fixtures / "MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx"),
        "hist_all_programs_3yr_xlsx": _sha256(
            fixtures / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx"
        ),
        "hist_ex_llc_3yr_xlsx": _sha256(fixtures / "Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx"),
        "hist_llc_3yr_xlsx": _sha256(fixtures / "Historical Counterparty Risk Graphs - LLC 3 Year.xlsx"),
        "monthly_pptx": _sha256(fixtures / "Monthly Counterparty Exposure Report.pptx"),
    }
    assert manifest["input_hashes"] == expected_hashes

    for variant in ("all_programs", "ex_trend", "trend"):
        assert variant in manifest["top_exposures"]
        assert variant in manifest["top_changes_per_variant"]
