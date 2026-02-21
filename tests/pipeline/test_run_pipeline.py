"""Integration-style tests for pipeline orchestration."""

from __future__ import annotations

import hashlib
import json
import sys
import types
from datetime import date
from pathlib import Path
from typing import Any

import pytest

import counter_risk.pipeline.run as run_module
from counter_risk.config import WorkflowConfig
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

    @property
    def active(self) -> _FakeWorksheet:
        return self._sheets[self.sheetnames[0]]

    def __getitem__(self, item: str) -> _FakeWorksheet:
        return self._sheets[item]

    def save(self, path: Path) -> None:
        self.saved_paths.append(path)

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_pandas(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = types.SimpleNamespace(DataFrame=_FakeDataFrame)
    monkeypatch.setitem(sys.modules, "pandas", fake_module)


@pytest.fixture(autouse=True)
def patch_repo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("counter_risk.pipeline.run._resolve_repo_root", lambda: tmp_path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _minimal_parsed_by_variant() -> dict[str, dict[str, _FakeDataFrame]]:
    totals = _FakeDataFrame(
        records=[{"counterparty": "Counterparty A", "Notional": 1.0, "NotionalChange": 0.5}]
    )
    futures = _FakeDataFrame(
        records=[
            {
                "account": "account-a",
                "description": "desc",
                "class": "class-a",
                "fcm": "fcm-a",
                "clearing_house": "ch-a",
                "notional": 1.0,
            }
        ]
    )
    return {
        "all_programs": {"totals": totals, "futures": futures},
        "ex_trend": {"totals": totals, "futures": futures},
        "trend": {"totals": totals, "futures": futures},
    }


def test_run_pipeline_writes_expected_outputs_and_manifest(
    tmp_path: Path, fake_pandas: None
) -> None:
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

    assert run_dir == tmp_path / "runs" / "2025-12-31"
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
        assert not Path(output_path).is_absolute()
        assert (run_dir / output_path).exists(), f"Manifest references missing path: {output_path}"

    assert "PPT links not refreshed; COM refresh skipped" in manifest["warnings"]

    expected_hashes = {
        "mosers_all_programs_xlsx": _sha256(
            fixtures / "MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx"
        ),
        "mosers_ex_trend_xlsx": _sha256(
            fixtures / "MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx"
        ),
        "mosers_trend_xlsx": _sha256(
            fixtures / "MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx"
        ),
        "hist_all_programs_3yr_xlsx": _sha256(
            fixtures / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx"
        ),
        "hist_ex_llc_3yr_xlsx": _sha256(
            fixtures / "Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx"
        ),
        "hist_llc_3yr_xlsx": _sha256(
            fixtures / "Historical Counterparty Risk Graphs - LLC 3 Year.xlsx"
        ),
        "monthly_pptx": _sha256(fixtures / "Monthly Counterparty Exposure Report.pptx"),
    }
    assert manifest["input_hashes"] == expected_hashes

    for variant in ("all_programs", "ex_trend", "trend"):
        assert variant in manifest["top_exposures"]
        assert variant in manifest["top_changes_per_variant"]


def test_run_pipeline_generates_all_programs_mosers_from_raw_nisa_input(
    tmp_path: Path, fake_pandas: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixtures = Path("tests/fixtures")
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "\n".join(
            [
                "as_of_date: 2025-12-31",
                f"raw_nisa_all_programs_xlsx: {fixtures / 'NISA Monthly All Programs - Raw.xlsx'}",
                f"mosers_ex_trend_xlsx: {fixtures / 'MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx'}",
                f"mosers_trend_xlsx: {fixtures / 'MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx'}",
                f"hist_all_programs_3yr_xlsx: {fixtures / 'Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx'}",
                f"hist_ex_llc_3yr_xlsx: {fixtures / 'Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx'}",
                f"hist_llc_3yr_xlsx: {fixtures / 'Historical Counterparty Risk Graphs - LLC 3 Year.xlsx'}",
                f"monthly_pptx: {fixtures / 'Monthly Counterparty Exposure Report.pptx'}",
                f"output_root: {tmp_path / 'runs'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    # Keep the raw-NISA generation path real, but stub downstream heavy stages
    # that are covered by dedicated integration tests.
    monkeypatch.setattr(
        "counter_risk.pipeline.run._parse_inputs", lambda _: _minimal_parsed_by_variant()
    )
    monkeypatch.setattr(
        "counter_risk.pipeline.run._update_historical_outputs",
        lambda *, run_dir, config, parsed_by_variant, as_of_date, warnings: [],
    )
    monkeypatch.setattr(
        "counter_risk.pipeline.run._write_outputs",
        lambda *, run_dir, config, warnings: (
            [],
            run_module.PptProcessingResult(status=run_module.PptProcessingStatus.SUCCESS),
        ),
    )

    run_dir = run_pipeline(config_path)

    generated_mosers_output = run_dir / "all_programs-mosers-input.xlsx"
    intermediate_generated_output = run_dir / "_generated" / "all_programs-generated-mosers.xlsx"
    assert generated_mosers_output.exists()
    assert intermediate_generated_output.exists()

    from openpyxl import load_workbook  # type: ignore[import-untyped]

    workbook = load_workbook(generated_mosers_output, read_only=True, data_only=True)
    try:
        assert workbook.sheetnames == ["CPRS - CH", "CPRS - FCM"]
    finally:
        workbook.close()

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "raw_nisa_all_programs_xlsx" in manifest["input_hashes"]
    assert "Generated All Programs MOSERS workbook from raw NISA input" in manifest["warnings"]


def test_prepare_runtime_config_generates_and_copies_raw_nisa_mosers_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    raw_nisa = tmp_path / "raw.xlsx"
    raw_nisa.write_text("raw", encoding="utf-8")
    ex_trend = tmp_path / "ex.xlsx"
    ex_trend.write_text("ex", encoding="utf-8")
    trend = tmp_path / "trend.xlsx"
    trend.write_text("trend", encoding="utf-8")
    hist_all = tmp_path / "hist_all.xlsx"
    hist_all.write_text("hist_all", encoding="utf-8")
    hist_ex = tmp_path / "hist_ex.xlsx"
    hist_ex.write_text("hist_ex", encoding="utf-8")
    hist_trend = tmp_path / "hist_trend.xlsx"
    hist_trend.write_text("hist_trend", encoding="utf-8")
    monthly_pptx = tmp_path / "monthly.pptx"
    monthly_pptx.write_text("ppt", encoding="utf-8")

    generated_calls: list[dict[str, Any]] = []

    def _fake_generate_mosers_workbook(
        *, raw_nisa_path: Path, output_path: Path, as_of_date: date
    ) -> Path:
        generated_calls.append(
            {
                "raw_nisa_path": raw_nisa_path,
                "output_path": output_path,
                "as_of_date": as_of_date,
            }
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"generated-workbook")
        return output_path

    monkeypatch.setattr(run_module, "generate_mosers_workbook", _fake_generate_mosers_workbook)

    config = WorkflowConfig(
        as_of_date=date(2025, 12, 31),
        raw_nisa_all_programs_xlsx=raw_nisa,
        mosers_all_programs_xlsx=None,
        mosers_ex_trend_xlsx=ex_trend,
        mosers_trend_xlsx=trend,
        hist_all_programs_3yr_xlsx=hist_all,
        hist_ex_llc_3yr_xlsx=hist_ex,
        hist_llc_3yr_xlsx=hist_trend,
        monthly_pptx=monthly_pptx,
        output_root=tmp_path / "runs",
    )
    warnings: list[str] = []

    runtime_config = run_module._prepare_runtime_config(
        config=config,
        run_dir=run_dir,
        as_of_date=date(2025, 12, 31),
        warnings=warnings,
    )

    generated_path = run_dir / "_generated" / "all_programs-generated-mosers.xlsx"
    canonical_path = run_dir / "all_programs-mosers-input.xlsx"

    assert generated_calls == [
        {
            "raw_nisa_path": raw_nisa,
            "output_path": generated_path,
            "as_of_date": date(2025, 12, 31),
        }
    ]
    assert generated_path.exists()
    assert canonical_path.exists()
    assert generated_path.read_bytes() == canonical_path.read_bytes()
    assert runtime_config.mosers_all_programs_xlsx == canonical_path
    assert "Generated All Programs MOSERS workbook from raw NISA input" in warnings


def _write_valid_config(tmp_path: Path, output_root: Path) -> Path:
    fixtures = Path("tests/fixtures")
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
    return config_path


def test_run_pipeline_wraps_parse_errors(
    tmp_path: Path, fake_pandas: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_valid_config(tmp_path=tmp_path, output_root=tmp_path / "runs")

    def _boom(_: dict[str, Path]) -> dict[str, dict[str, Any]]:
        raise ValueError("bad parser input")

    monkeypatch.setattr("counter_risk.pipeline.run._parse_inputs", _boom)

    with pytest.raises(RuntimeError, match="Pipeline failed during parse stage") as exc_info:
        run_pipeline(config_path)

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "bad parser input" in str(exc_info.value.__cause__)


def test_run_pipeline_wraps_parse_validation_errors(
    tmp_path: Path, fake_pandas: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_valid_config(tmp_path=tmp_path, output_root=tmp_path / "runs")

    malformed = {
        "all_programs": {
            "totals": _FakeDataFrame(records=[{"counterparty": "A", "Notional": 1.0}]),
            "futures": _FakeDataFrame(records=[]),
        },
        "ex_trend": {
            "totals": _FakeDataFrame(records=[{"counterparty": "B", "Notional": 2.0}]),
            "futures": _FakeDataFrame(records=[]),
        },
        "trend": {
            "totals": _FakeDataFrame(records=[]),
            "futures": _FakeDataFrame(records=[{"account": "Acct"}]),
        },
    }

    def _bad_parse(_: dict[str, Path]) -> dict[str, dict[str, Any]]:
        return malformed

    monkeypatch.setattr("counter_risk.pipeline.run._parse_inputs", _bad_parse)

    with pytest.raises(RuntimeError, match="Pipeline failed during parse stage") as exc_info:
        run_pipeline(config_path)

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "missing required columns" in str(exc_info.value.__cause__)


def test_run_pipeline_warn_mode_writes_mapping_updates_and_completes(
    tmp_path: Path, fake_pandas: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_valid_config(tmp_path=tmp_path, output_root=tmp_path / "runs")
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n".join(
            [
                "reconciliation:",
                "  fail_policy: warn",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "counter_risk.pipeline.run._parse_inputs", lambda _: _minimal_parsed_by_variant()
    )
    monkeypatch.setattr(
        "counter_risk.pipeline.run._extract_historical_series_headers_by_sheet",
        lambda _: {"Total": ("Legacy Counterparty",)},
    )
    monkeypatch.setattr(
        "counter_risk.pipeline.run._update_historical_outputs",
        lambda *, run_dir, config, parsed_by_variant, as_of_date, warnings: [],
    )
    monkeypatch.setattr(
        "counter_risk.pipeline.run._write_outputs",
        lambda *, run_dir, config, warnings: (
            [],
            run_module.PptProcessingResult(status=run_module.PptProcessingStatus.SUCCESS),
        ),
    )

    run_dir = run_pipeline(config_path)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    mapping_updates = run_dir / "NEEDS_MAPPING_UPDATES.txt"

    assert mapping_updates.exists()
    text = mapping_updates.read_text(encoding="utf-8")
    assert "run_identifier: 2025-12-31" in text
    assert "fail_policy: warn" in text
    assert "missing_from_historical_headers" in text
    assert any("Reconciliation summary:" in warning for warning in manifest["warnings"])


def test_run_pipeline_strict_mode_fails_when_reconciliation_has_gaps(
    tmp_path: Path, fake_pandas: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_valid_config(tmp_path=tmp_path, output_root=tmp_path / "runs")
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n".join(
            [
                "reconciliation:",
                "  fail_policy: strict",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "counter_risk.pipeline.run._parse_inputs", lambda _: _minimal_parsed_by_variant()
    )
    monkeypatch.setattr(
        "counter_risk.pipeline.run._extract_historical_series_headers_by_sheet",
        lambda _: {"Total": ("Legacy Counterparty",)},
    )

    with pytest.raises(RuntimeError, match="Pipeline failed during parse stage") as exc_info:
        run_pipeline(config_path)

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "Reconciliation strict mode failed" in str(exc_info.value.__cause__)


def test_run_pipeline_wraps_output_write_errors(
    tmp_path: Path, fake_pandas: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_valid_config(tmp_path=tmp_path, output_root=tmp_path / "runs")
    monkeypatch.setattr(
        "counter_risk.pipeline.run._parse_inputs", lambda _: _minimal_parsed_by_variant()
    )
    monkeypatch.setattr(
        "counter_risk.pipeline.run._update_historical_outputs",
        lambda *, run_dir, config, parsed_by_variant, as_of_date, warnings: [],
    )

    def _boom(*, run_dir: Path, config: Any, warnings: list[str]) -> list[Path]:
        _ = (run_dir, config, warnings)
        raise OSError("disk full")

    monkeypatch.setattr("counter_risk.pipeline.run._write_outputs", _boom)

    with pytest.raises(RuntimeError, match="Pipeline failed during output write stage") as exc_info:
        run_pipeline(config_path)

    assert isinstance(exc_info.value.__cause__, OSError)
    assert "disk full" in str(exc_info.value.__cause__)


def test_run_pipeline_wraps_input_validation_errors(
    tmp_path: Path, fake_pandas: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_valid_config(tmp_path=tmp_path, output_root=tmp_path / "runs")

    def _boom(_: dict[str, Path]) -> None:
        raise FileNotFoundError("missing source workbook")

    monkeypatch.setattr("counter_risk.pipeline.run._validate_input_files", _boom)

    with pytest.raises(
        RuntimeError, match="Pipeline failed during input validation stage"
    ) as exc_info:
        run_pipeline(config_path)

    assert isinstance(exc_info.value.__cause__, FileNotFoundError)
    assert "missing source workbook" in str(exc_info.value.__cause__)


def test_run_pipeline_wraps_compute_errors(
    tmp_path: Path, fake_pandas: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_valid_config(tmp_path=tmp_path, output_root=tmp_path / "runs")

    def _boom(
        _: dict[str, dict[str, Any]],
    ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
        raise ValueError("bad compute inputs")

    monkeypatch.setattr("counter_risk.pipeline.run._compute_metrics", _boom)

    with pytest.raises(RuntimeError, match="Pipeline failed during compute stage") as exc_info:
        run_pipeline(config_path)

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "bad compute inputs" in str(exc_info.value.__cause__)


def test_run_pipeline_wraps_historical_update_errors(
    tmp_path: Path, fake_pandas: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_valid_config(tmp_path=tmp_path, output_root=tmp_path / "runs")

    def _boom(
        *,
        run_dir: Path,
        config: Any,
        parsed_by_variant: dict[str, dict[str, Any]],
        as_of_date: date,
        warnings: list[str],
    ) -> list[Path]:
        _ = (run_dir, config, parsed_by_variant, as_of_date, warnings)
        raise OSError("historical workbook write failed")

    monkeypatch.setattr("counter_risk.pipeline.run._update_historical_outputs", _boom)

    with pytest.raises(
        RuntimeError, match="Pipeline failed during historical update stage"
    ) as exc_info:
        run_pipeline(config_path)

    assert isinstance(exc_info.value.__cause__, OSError)
    assert "historical workbook write failed" in str(exc_info.value.__cause__)


def test_run_pipeline_wraps_manifest_generation_errors(
    tmp_path: Path, fake_pandas: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_valid_config(tmp_path=tmp_path, output_root=tmp_path / "runs")
    monkeypatch.setattr(
        "counter_risk.pipeline.run._parse_inputs", lambda _: _minimal_parsed_by_variant()
    )
    monkeypatch.setattr(
        "counter_risk.pipeline.run._update_historical_outputs",
        lambda *, run_dir, config, parsed_by_variant, as_of_date, warnings: [],
    )
    monkeypatch.setattr(
        "counter_risk.pipeline.run._write_outputs",
        lambda *, run_dir, config, warnings: (
            [],
            run_module.PptProcessingResult(status=run_module.PptProcessingStatus.SUCCESS),
        ),
    )

    def _boom(self: Any, *, run_dir: Path, manifest: dict[str, Any]) -> Path:
        _ = (self, run_dir, manifest)
        raise OSError("manifest disk error")

    monkeypatch.setattr("counter_risk.pipeline.run.ManifestBuilder.write", _boom)

    with pytest.raises(
        RuntimeError, match="Pipeline failed during manifest generation stage"
    ) as exc_info:
        run_pipeline(config_path)

    assert isinstance(exc_info.value.__cause__, OSError)
    assert "manifest disk error" in str(exc_info.value.__cause__)


def test_run_pipeline_passes_as_of_date_and_parsed_inputs_to_historical_update(
    tmp_path: Path, fake_pandas: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_valid_config(tmp_path=tmp_path, output_root=tmp_path / "runs")
    calls: list[dict[str, Any]] = []

    def _capture(
        *,
        run_dir: Path,
        config: Any,
        parsed_by_variant: dict[str, dict[str, Any]],
        as_of_date: date,
        warnings: list[str],
    ) -> list[Path]:
        _ = config
        calls.append(
            {
                "run_dir": run_dir,
                "variants": sorted(parsed_by_variant.keys()),
                "as_of_date": as_of_date,
                "warnings": warnings,
            }
        )
        return []

    monkeypatch.setattr("counter_risk.pipeline.run._update_historical_outputs", _capture)

    run_dir = run_pipeline(config_path)

    assert run_dir == tmp_path / "runs" / "2025-12-31"
    assert len(calls) == 1
    assert calls[0]["as_of_date"] == date(2025, 12, 31)
    assert calls[0]["variants"] == ["all_programs", "ex_trend", "trend"]


def test_run_pipeline_invokes_ppt_link_refresh(
    tmp_path: Path, fake_pandas: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_valid_config(tmp_path=tmp_path, output_root=tmp_path / "runs")
    monkeypatch.setattr(
        "counter_risk.pipeline.run._parse_inputs", lambda _: _minimal_parsed_by_variant()
    )
    monkeypatch.setattr(
        "counter_risk.pipeline.run._update_historical_outputs",
        lambda *, run_dir, config, parsed_by_variant, as_of_date, warnings: [],
    )
    seen: dict[str, Path] = {}

    def _refresh(pptx_path: Path) -> bool:
        seen["path"] = pptx_path
        return True

    monkeypatch.setattr("counter_risk.pipeline.run._refresh_ppt_links", _refresh)

    run_dir = run_pipeline(config_path)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    assert seen["path"] == run_dir / "Monthly Counterparty Exposure Report.pptx"
    assert "PPT links not refreshed; COM refresh skipped" not in manifest["warnings"]


def test_run_pipeline_ignores_config_output_root_for_run_directory(
    tmp_path: Path, fake_pandas: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_valid_config(
        tmp_path=tmp_path, output_root=tmp_path / "different-output-root"
    )
    monkeypatch.setattr(
        "counter_risk.pipeline.run._parse_inputs", lambda _: _minimal_parsed_by_variant()
    )
    monkeypatch.setattr(
        "counter_risk.pipeline.run._update_historical_outputs",
        lambda *, run_dir, config, parsed_by_variant, as_of_date, warnings: [],
    )
    monkeypatch.setattr(
        "counter_risk.pipeline.run._write_outputs",
        lambda *, run_dir, config, warnings: (
            [],
            run_module.PptProcessingResult(status=run_module.PptProcessingStatus.SUCCESS),
        ),
    )

    run_dir = run_pipeline(config_path)

    assert run_dir == tmp_path / "runs" / "2025-12-31"
    assert not (tmp_path / "different-output-root" / "2025-12-31").exists()


def test_run_pipeline_wraps_config_validation_errors_for_output_root_file(
    tmp_path: Path, fake_pandas: None
) -> None:
    output_root_file = tmp_path / "runs"
    output_root_file.write_text("not-a-directory", encoding="utf-8")
    config_path = _write_valid_config(tmp_path=tmp_path, output_root=output_root_file)

    with pytest.raises(RuntimeError, match="Pipeline failed during config validation") as exc_info:
        run_pipeline(config_path)

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "output_root must be a directory path" in str(exc_info.value.__cause__)


def test_run_pipeline_wraps_config_validation_errors_for_invalid_ppt_extension(
    tmp_path: Path, fake_pandas: None
) -> None:
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
                f"monthly_pptx: {fixtures / 'MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx'}",
                f"output_root: {output_root}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="Pipeline failed during config validation") as exc_info:
        run_pipeline(config_path)

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "Invalid file type for monthly_pptx: expected .pptx" in str(exc_info.value.__cause__)


def test_run_pipeline_wraps_config_load_errors(
    tmp_path: Path, fake_pandas: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "missing.yml"

    def _boom(_: Path) -> Any:
        raise ValueError("config parse failed")

    monkeypatch.setattr("counter_risk.pipeline.run.load_config", _boom)

    with pytest.raises(RuntimeError, match="Pipeline failed during config load") as exc_info:
        run_pipeline(config_path)

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "config parse failed" in str(exc_info.value.__cause__)


def test_run_pipeline_wraps_run_directory_setup_errors(
    tmp_path: Path, fake_pandas: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_valid_config(tmp_path=tmp_path, output_root=tmp_path / "runs")

    def _boom(self: Path, parents: bool, exist_ok: bool) -> None:
        _ = (self, parents, exist_ok)
        raise OSError("permission denied")

    monkeypatch.setattr("counter_risk.pipeline.run.Path.mkdir", _boom)

    with pytest.raises(
        RuntimeError, match="Pipeline failed during run directory setup stage"
    ) as exc_info:
        run_pipeline(config_path)

    assert isinstance(exc_info.value.__cause__, OSError)
    assert "permission denied" in str(exc_info.value.__cause__)


def test_merge_historical_workbook_prefers_configured_total_sheet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workbook_path = tmp_path / "hist.xlsx"
    workbook_path.write_bytes(b"fixture")

    decoy = _FakeWorksheet("A Decoy")
    decoy.set_value(1, 1, "Date")
    decoy.set_value(1, 2, "Wrong")
    decoy.set_value(1, 3, "Wrong")
    decoy.set_value(2, 1, "2025-12-31")

    target = _FakeWorksheet("Total")
    target.set_value(1, 1, "Date")
    target.set_value(1, 2, "Barclays")
    target.set_value(1, 3, "Citibank")
    target.set_value(2, 1, "2025-12-31")

    workbook = _FakeWorkbook({"A Decoy": decoy, "Total": target})
    monkeypatch.setitem(
        sys.modules, "openpyxl", types.SimpleNamespace(load_workbook=lambda filename: workbook)
    )

    run_module._merge_historical_workbook(
        workbook_path=workbook_path,
        variant="all_programs",
        as_of_date=date(2026, 2, 13),
        totals_records=[{"Notional": 10.0, "counterparty": "A"}],
        warnings=[],
    )

    assert target.cell(row=3, column=1).value == "2026-02-13"
    assert target.cell(row=3, column=2).value == pytest.approx(10.0)
    assert target.cell(row=3, column=3).value == 1
    assert decoy.cell(row=3, column=1).value is None


def test_merge_historical_workbook_uses_deterministic_fallback_sheet_when_preferred_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workbook_path = tmp_path / "hist.xlsx"
    workbook_path.write_bytes(b"fixture")

    alpha = _FakeWorksheet("Alpha")
    alpha.set_value(1, 1, "Date")
    alpha.set_value(1, 2, "Series A")
    alpha.set_value(1, 3, "Series B")
    alpha.set_value(2, 1, "2025-12-31")

    zulu = _FakeWorksheet("Zulu")
    zulu.set_value(1, 1, "Date")
    zulu.set_value(1, 2, "Series A")
    zulu.set_value(1, 3, "Series B")
    zulu.set_value(2, 1, "2025-12-31")

    workbook = _FakeWorkbook({"Zulu": zulu, "Alpha": alpha})
    monkeypatch.setitem(
        sys.modules, "openpyxl", types.SimpleNamespace(load_workbook=lambda filename: workbook)
    )

    run_module._merge_historical_workbook(
        workbook_path=workbook_path,
        variant="unknown_variant",
        as_of_date=date(2026, 2, 13),
        totals_records=[
            {"Notional": 20.0, "counterparty": "A"},
            {"Notional": 5.0, "counterparty": "B"},
        ],
        warnings=[],
    )

    assert alpha.cell(row=3, column=1).value == "2026-02-13"
    assert alpha.cell(row=3, column=2).value == pytest.approx(25.0)
    assert alpha.cell(row=3, column=3).value == 2
    assert zulu.cell(row=3, column=1).value is None


def test_merge_historical_workbook_fails_fast_when_required_headers_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workbook_path = tmp_path / "hist.xlsx"
    workbook_path.write_bytes(b"fixture")

    broken = _FakeWorksheet("Total")
    broken.set_value(1, 1, "Date")
    broken.set_value(1, 2, "")
    broken.set_value(1, 3, "Series B")
    broken.set_value(2, 1, "2025-12-31")

    workbook = _FakeWorkbook({"Total": broken})
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

    message = str(exc_info.value.__cause__)
    assert "missing required columns" in message
    assert "Total" in message
    assert "value series 1" in message
    assert broken.cell(row=3, column=1).value is None
