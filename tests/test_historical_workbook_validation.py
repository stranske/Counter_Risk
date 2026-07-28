"""Historical workbook validation coverage for pipeline workbook append behavior."""

from __future__ import annotations

import sys
import types
from datetime import date
from pathlib import Path
from typing import Any

import pytest

import counter_risk.pipeline.run as run_module
from counter_risk.config import OutputGeneratorConfig, WorkflowConfig
from counter_risk.outputs.base import OutputContext

_EXPOSURE_SUMMARY_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "nisa"
    / "NISA_Monthly_Exposure_Summary_sanitized.xlsx"
)


class _FakeCell:
    def __init__(self, value: Any = None) -> None:
        self.value = value
        self.number_format = "General"
        # Minimal openpyxl Cell surface touched by appended-row presentation
        # copying. has_style is False because a bare fake carries no style, so the
        # copy is skipped here.
        self.has_style = False
        self.font = None
        self.fill = None
        self.border = None
        self.alignment = None


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
    """Build a fake "Total" sheet — the first (and, in these tests, only) sheet
    listed for the "all_programs" variant in
    ``run_module._HISTORICAL_SHEET_SPECS_BY_VARIANT``. Sheets not present in the
    fake workbook are silently skipped by ``_merge_historical_workbook``, so a
    single-sheet fake workbook exercises just the "Total" spec."""
    target = _FakeWorksheet("Total")
    target.set_value(1, 1, "Date")
    target.set_value(1, 2, first_header)
    target.set_value(1, 3, second_header)
    target.set_value(2, 1, date(2026, 1, 31))
    return target


def test_historical_validation_missing_header_includes_sheet_and_missing_columns(
    workbook_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workbook = _FakeWorkbook({"Total": _base_target_sheet(first_header=None, second_header=None)})
    monkeypatch.setitem(
        sys.modules, "openpyxl", types.SimpleNamespace(load_workbook=lambda filename: workbook)
    )

    with pytest.raises(RuntimeError, match="Failed to update historical workbook") as exc_info:
        run_module._merge_historical_workbook(
            workbook_path=workbook_path,
            variant="all_programs",
            as_of_date=date(2026, 2, 13),
            cprs_ch_records=[{"Notional": 10.0, "Counterparty": "A"}],
            warnings=[],
        )

    cause_message = str(exc_info.value.__cause__)
    assert "Total" in cause_message
    assert "missing required columns" in cause_message
    assert "at least one series column" in cause_message
    assert workbook.saved_paths == []


def test_historical_validation_with_decoy_and_target_sheet_appends_only_to_target(
    workbook_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decoy = _FakeWorksheet("A Decoy")
    decoy.set_value(1, 1, "Date")
    decoy.set_value(1, 2, "Wrong")
    decoy.set_value(1, 3, "Wrong")
    decoy.set_value(2, 1, date(2026, 1, 31))

    target = _base_target_sheet(first_header="Series A", second_header="Series B")

    workbook = _FakeWorkbook({"A Decoy": decoy, "Total": target})
    monkeypatch.setitem(
        sys.modules, "openpyxl", types.SimpleNamespace(load_workbook=lambda filename: workbook)
    )

    run_module._merge_historical_workbook(
        workbook_path=workbook_path,
        variant="all_programs",
        as_of_date=date(2026, 2, 13),
        cprs_ch_records=[
            {"Notional": 20.0, "Counterparty": "Series A"},
            {"Notional": 5.0, "Counterparty": "Series B"},
        ],
        warnings=[],
    )

    assert target.cell(row=3, column=1).value == date(2026, 2, 13)
    assert target.cell(row=3, column=2).value == pytest.approx(20.0)
    assert target.cell(row=3, column=3).value == pytest.approx(5.0)
    # "A Decoy" is not one of the sheets listed for "all_programs" — untouched.
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
        cprs_ch_records=[
            {"Notional": 30.0, "Counterparty": "Series A"},
            {"Notional": 12.0, "Counterparty": "Series B"},
            {"Notional": 3.0, "Counterparty": "Series B"},
        ],
        warnings=[],
    )

    assert source_path.read_bytes() == b"source"
    assert run_copy_path.read_bytes() == b"updated"
    assert target.cell(row=3, column=1).value == date(2026, 2, 13)
    assert target.cell(row=3, column=2).value == pytest.approx(30.0)
    assert target.cell(row=3, column=3).value == pytest.approx(15.0)


def test_historical_workbook_update_normalized_headers_and_run_dir_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs_dir = tmp_path / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    all_programs_input = inputs_dir / "all_programs.xlsx"
    ex_trend_input = inputs_dir / "ex_trend.xlsx"
    trend_input = inputs_dir / "trend.xlsx"
    monthly_pptx = inputs_dir / "monthly.pptx"
    for file_path in (all_programs_input, ex_trend_input, trend_input, monthly_pptx):
        file_path.write_bytes(b"input")

    hist_all = inputs_dir / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx"
    hist_ex = inputs_dir / "Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx"
    hist_trend = inputs_dir / "Historical Counterparty Risk Graphs - LLC 3 Year.xlsx"
    for file_path in (hist_all, hist_ex, hist_trend):
        file_path.write_bytes(b"source")

    run_dir = tmp_path / "runs" / "2026-02-13"
    run_dir.mkdir(parents=True)
    config = WorkflowConfig(
        as_of_date=date(2026, 2, 13),
        mosers_all_programs_xlsx=all_programs_input,
        mosers_ex_trend_xlsx=ex_trend_input,
        mosers_trend_xlsx=trend_input,
        hist_all_programs_3yr_xlsx=hist_all,
        hist_ex_llc_3yr_xlsx=hist_ex,
        hist_llc_3yr_xlsx=hist_trend,
        monthly_pptx=monthly_pptx,
        output_root=tmp_path / "unused-output-root",
    )

    sheet_by_path: dict[Path, _FakeWorksheet] = {}

    def _make_sheet() -> _FakeWorksheet:
        worksheet = _FakeWorksheet("Total")
        worksheet.set_value(1, 1, "  AS  OF   DATE ")
        worksheet.set_value(1, 2, "Series A")
        worksheet.set_value(1, 3, "Series B")
        worksheet.set_value(2, 1, date(2026, 1, 31))
        return worksheet

    def _load_workbook(*, filename: Path) -> _FakeWorkbook:
        worksheet = _make_sheet()
        sheet_by_path[filename] = worksheet
        return _FakeWorkbook({"Total": worksheet})

    monkeypatch.setitem(
        sys.modules, "openpyxl", types.SimpleNamespace(load_workbook=_load_workbook)
    )

    output_paths = run_module._update_historical_outputs(
        run_dir=run_dir,
        config=config,
        parsed_by_variant={
            "all_programs": {"cprs_ch": [{"Counterparty": "Series A", "Notional": 10.0}]},
            "ex_trend": {"cprs_ch": [{"Counterparty": "B", "Notional": 4.0}]},
            "trend": {"cprs_ch": [{"Counterparty": "C", "Notional": 7.0}]},
        },
        as_of_date=date(2026, 2, 13),
        warnings=[],
    )

    assert len(output_paths) == 3
    assert all(path.is_relative_to(run_dir) for path in output_paths)
    assert all(path.read_bytes() == b"updated" for path in output_paths)
    assert hist_all.read_bytes() == b"source"

    all_programs_copy = run_dir / hist_all.name
    assert sheet_by_path[all_programs_copy].cell(row=3, column=1).value == date(2026, 2, 13)
    assert sheet_by_path[all_programs_copy].cell(row=3, column=2).value == pytest.approx(10.0)
    assert sheet_by_path[all_programs_copy].cell(row=3, column=3).value == pytest.approx(0.0)


def test_historical_update_appends_as_of_date_not_run_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs_dir = tmp_path / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    all_programs_input = inputs_dir / "all_programs.xlsx"
    ex_trend_input = inputs_dir / "ex_trend.xlsx"
    trend_input = inputs_dir / "trend.xlsx"
    monthly_pptx = inputs_dir / "monthly.pptx"
    for file_path in (all_programs_input, ex_trend_input, trend_input, monthly_pptx):
        file_path.write_bytes(b"input")

    hist_all = inputs_dir / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx"
    hist_ex = inputs_dir / "Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx"
    hist_trend = inputs_dir / "Historical Counterparty Risk Graphs - LLC 3 Year.xlsx"
    for file_path in (hist_all, hist_ex, hist_trend):
        file_path.write_bytes(b"source")

    run_dir = tmp_path / "runs" / "2026-02-13__run_2026-02-14"
    run_dir.mkdir(parents=True)
    config = WorkflowConfig(
        as_of_date=date(2026, 2, 13),
        run_date=date(2026, 2, 14),
        mosers_all_programs_xlsx=all_programs_input,
        mosers_ex_trend_xlsx=ex_trend_input,
        mosers_trend_xlsx=trend_input,
        hist_all_programs_3yr_xlsx=hist_all,
        hist_ex_llc_3yr_xlsx=hist_ex,
        hist_llc_3yr_xlsx=hist_trend,
        monthly_pptx=monthly_pptx,
        output_root=tmp_path / "unused-output-root",
    )

    sheet_by_path: dict[Path, _FakeWorksheet] = {}

    def _make_sheet() -> _FakeWorksheet:
        worksheet = _FakeWorksheet("Total")
        worksheet.set_value(1, 1, "Date")
        worksheet.set_value(1, 2, "Series A")
        worksheet.set_value(1, 3, "Series B")
        worksheet.set_value(2, 1, date(2026, 1, 31))
        return worksheet

    def _load_workbook(*, filename: Path) -> _FakeWorkbook:
        worksheet = _make_sheet()
        sheet_by_path[filename] = worksheet
        return _FakeWorkbook({"Total": worksheet})

    monkeypatch.setitem(
        sys.modules, "openpyxl", types.SimpleNamespace(load_workbook=_load_workbook)
    )

    output_paths = run_module._update_historical_outputs(
        run_dir=run_dir,
        config=config,
        parsed_by_variant={
            "all_programs": {"cprs_ch": [{"Counterparty": "A", "Notional": 10.0}]},
            "ex_trend": {"cprs_ch": [{"Counterparty": "B", "Notional": 4.0}]},
            "trend": {"cprs_ch": [{"Counterparty": "C", "Notional": 7.0}]},
        },
        as_of_date=date(2026, 2, 13),
        warnings=[],
    )

    assert len(output_paths) == 3
    all_programs_copy = run_dir / hist_all.name
    appended_date = sheet_by_path[all_programs_copy].cell(row=3, column=1).value
    assert appended_date == date(2026, 2, 13)
    assert appended_date != config.run_date


def test_historical_update_delegates_to_output_generator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_programs_input = tmp_path / "all_programs.xlsx"
    ex_trend_input = tmp_path / "ex_trend.xlsx"
    trend_input = tmp_path / "trend.xlsx"
    monthly_pptx = tmp_path / "monthly.pptx"
    hist_all = tmp_path / "hist_all.xlsx"
    hist_ex = tmp_path / "hist_ex.xlsx"
    hist_trend = tmp_path / "hist_trend.xlsx"
    for file_path in (
        all_programs_input,
        ex_trend_input,
        trend_input,
        monthly_pptx,
        hist_all,
        hist_ex,
        hist_trend,
    ):
        file_path.write_bytes(b"placeholder")

    run_dir = tmp_path / "runs" / "2026-02-13"
    run_dir.mkdir(parents=True)
    config = WorkflowConfig(
        mosers_all_programs_xlsx=all_programs_input,
        mosers_ex_trend_xlsx=ex_trend_input,
        mosers_trend_xlsx=trend_input,
        hist_all_programs_3yr_xlsx=hist_all,
        hist_ex_llc_3yr_xlsx=hist_ex,
        hist_llc_3yr_xlsx=hist_trend,
        monthly_pptx=monthly_pptx,
    )
    warnings = ["warning 1"]
    # This test mocks _build_historical_workbook_output_generator entirely, so
    # parsed_by_variant's contents are never read — only its identity is checked.
    parsed_by_variant = {
        "all_programs": {"cprs_ch": [{"Counterparty": "A", "Notional": 10.0}]},
        "ex_trend": {"cprs_ch": [{"Counterparty": "B", "Notional": 4.0}]},
        "trend": {"cprs_ch": [{"Counterparty": "C", "Notional": 7.0}]},
    }
    generated_outputs = (run_dir / "hist_all.xlsx", run_dir / "hist_ex.xlsx")
    captured: dict[str, Any] = {}

    class _FakeGenerator:
        def __init__(
            self, *, parsed_by_variant: dict[str, dict[str, Any]], warnings: list[str]
        ) -> None:
            captured["parsed_by_variant"] = parsed_by_variant
            captured["warnings"] = warnings

        def generate(self, *, context: Any) -> tuple[Path, ...]:
            captured["context"] = context
            return generated_outputs

    monkeypatch.setattr(
        run_module,
        "_build_historical_workbook_output_generator",
        lambda *, parsed_by_variant, warnings: _FakeGenerator(
            parsed_by_variant=parsed_by_variant, warnings=warnings
        ),
    )

    output_paths = run_module._update_historical_outputs(
        run_dir=run_dir,
        config=config,
        parsed_by_variant=parsed_by_variant,
        as_of_date=date(2026, 2, 13),
        warnings=warnings,
    )

    assert output_paths == list(generated_outputs)
    assert captured["parsed_by_variant"] is parsed_by_variant
    assert captured["warnings"] is warnings
    context = captured["context"]
    assert context.config is config
    assert context.run_dir == run_dir
    assert context.as_of_date == date(2026, 2, 13)
    assert context.run_date == date(2026, 2, 13)
    assert context.warnings == tuple(warnings)


def test_historical_output_generator_builder_preserves_variant_merge_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_programs_input = tmp_path / "all_programs.xlsx"
    ex_trend_input = tmp_path / "ex_trend.xlsx"
    trend_input = tmp_path / "trend.xlsx"
    monthly_pptx = tmp_path / "monthly.pptx"
    hist_all = tmp_path / "hist_all.xlsx"
    hist_ex = tmp_path / "hist_ex.xlsx"
    hist_trend = tmp_path / "hist_trend.xlsx"
    for file_path in (
        all_programs_input,
        ex_trend_input,
        trend_input,
        monthly_pptx,
        hist_all,
        hist_ex,
        hist_trend,
    ):
        file_path.write_bytes(b"placeholder")

    run_dir = tmp_path / "runs" / "2026-02-13"
    run_dir.mkdir(parents=True)
    config = WorkflowConfig(
        mosers_all_programs_xlsx=all_programs_input,
        mosers_ex_trend_xlsx=ex_trend_input,
        mosers_trend_xlsx=trend_input,
        hist_all_programs_3yr_xlsx=hist_all,
        hist_ex_llc_3yr_xlsx=hist_ex,
        hist_llc_3yr_xlsx=hist_trend,
        monthly_pptx=monthly_pptx,
    )

    warnings: list[str] = []
    parsed_by_variant: dict[str, dict[str, Any]] = {
        # "skip-me" (a non-Mapping entry) exercises _records()'s filtering.
        "all_programs": {"cprs_ch": [{"Counterparty": "A", "Notional": 10.0}, "skip-me"]},
        "ex_trend": {"cprs_ch": [{"Counterparty": "B", "Notional": 4.0}]},
        "trend": {"cprs_ch": [{"Counterparty": "C", "Notional": 7.0}]},
    }

    merge_calls: list[tuple[Path, str, list[dict[str, Any]], list[str]]] = []

    def _fake_merge(
        *,
        workbook_path: Path,
        variant: str,
        as_of_date: date,
        cprs_ch_records: list[dict[str, Any]],
        formatting_profile: str | None = None,
        class_breakdown: dict[str, float] | None = None,
        warnings: list[str],
    ) -> None:
        _ = formatting_profile
        _ = class_breakdown
        assert as_of_date == date(2026, 2, 13)
        merge_calls.append((workbook_path, variant, cprs_ch_records, warnings))

    monkeypatch.setattr(run_module, "_merge_historical_workbook", _fake_merge)
    generator = run_module._build_historical_workbook_output_generator(
        parsed_by_variant=parsed_by_variant,
        warnings=warnings,
    )

    output_paths = generator.generate(
        context=OutputContext(
            config=config,
            run_dir=run_dir,
            as_of_date=date(2026, 2, 13),
            run_date=date(2026, 2, 13),
            warnings=tuple(warnings),
        )
    )

    assert output_paths == (
        run_dir / hist_all.name,
        run_dir / hist_ex.name,
        run_dir / hist_trend.name,
    )
    assert merge_calls == [
        (
            run_dir / hist_all.name,
            "all_programs",
            [{"Counterparty": "A", "Notional": 10.0}],
            warnings,
        ),
        (
            run_dir / hist_ex.name,
            "ex_trend",
            [{"Counterparty": "B", "Notional": 4.0}],
            warnings,
        ),
        (
            run_dir / hist_trend.name,
            "trend",
            [{"Counterparty": "C", "Notional": 7.0}],
            warnings,
        ),
    ]


def test_historical_update_wires_wal_generator_into_ex_llc_run_dir_copy(
    tmp_path: Path,
) -> None:
    """Registering the "historical_wal_workbook" builtin generator must append the
    WAL row into the *same* run_dir copy of hist_ex_llc_3yr_xlsx that the
    historical_workbook generator merges Notional/TIPS/etc. into (simulated here
    by pre-seeding that copy), not into the pristine original workbook."""
    openpyxl = pytest.importorskip("openpyxl")

    inputs_dir = tmp_path / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    all_programs_input = inputs_dir / "all_programs.xlsx"
    ex_trend_input = inputs_dir / "ex_trend.xlsx"
    trend_input = inputs_dir / "trend.xlsx"
    monthly_pptx = inputs_dir / "monthly.pptx"
    for file_path in (all_programs_input, ex_trend_input, trend_input, monthly_pptx):
        file_path.write_bytes(b"input")

    hist_all = inputs_dir / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx"
    hist_trend = inputs_dir / "Historical Counterparty Risk Graphs - LLC 3 Year.xlsx"
    for file_path in (hist_all, hist_trend):
        file_path.write_bytes(b"source")

    # hist_ex must be a real workbook with a real "WAL" sheet: append_wal_row uses
    # real openpyxl, unlike the faked-openpyxl merge tests elsewhere in this file.
    hist_ex = inputs_dir / "Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx"
    workbook = openpyxl.Workbook()
    wal_sheet = workbook.active
    wal_sheet.title = "WAL"
    wal_sheet.cell(row=2, column=1).value = "Date"
    wal_sheet.cell(row=2, column=2).value = "WAL TIPS REPO"
    wal_sheet.cell(row=3, column=1).value = date(2025, 12, 31)
    wal_sheet.cell(row=3, column=2).value = 2.0
    workbook.save(hist_ex)
    workbook.close()

    run_dir = tmp_path / "runs" / "2026-01-31"
    run_dir.mkdir(parents=True)

    config = WorkflowConfig(
        as_of_date=date(2026, 1, 31),
        mosers_all_programs_xlsx=all_programs_input,
        mosers_ex_trend_xlsx=ex_trend_input,
        mosers_trend_xlsx=trend_input,
        hist_all_programs_3yr_xlsx=hist_all,
        hist_ex_llc_3yr_xlsx=hist_ex,
        hist_llc_3yr_xlsx=hist_trend,
        monthly_pptx=monthly_pptx,
        exposure_summary_xlsx=_EXPOSURE_SUMMARY_FIXTURE,
        output_root=tmp_path / "unused-output-root",
        output_generators=(
            OutputGeneratorConfig(
                name="historical_workbook",
                registration="builtin:historical_workbook",
                stage="historical",
                enabled=False,
            ),
            OutputGeneratorConfig(
                name="historical_wal_workbook",
                registration="builtin:historical_wal_workbook",
                stage="historical",
            ),
        ),
    )

    # Simulate that historical_workbook already ran this run and produced this
    # run_dir copy (the WAL generator must target that copy, not the original).
    ex_run_copy = run_dir / hist_ex.name
    ex_run_copy.write_bytes(hist_ex.read_bytes())

    output_paths = run_module._update_historical_outputs(
        run_dir=run_dir,
        config=config,
        parsed_by_variant={
            "all_programs": {"cprs_ch": []},
            "ex_trend": {"cprs_ch": []},
            "trend": {"cprs_ch": []},
        },
        as_of_date=date(2026, 1, 31),
        warnings=[],
    )

    assert output_paths == [ex_run_copy]

    reloaded = openpyxl.load_workbook(ex_run_copy)
    try:
        reloaded_wal_sheet = reloaded["WAL"]
        appended_date = reloaded_wal_sheet.cell(row=4, column=1).value
        appended_wal = reloaded_wal_sheet.cell(row=4, column=2).value
    finally:
        reloaded.close()

    assert appended_date is not None
    assert appended_wal is not None
    assert appended_wal > 0

    # The pristine original (outside run_dir) must be untouched.
    original = openpyxl.load_workbook(hist_ex)
    try:
        original_wal_sheet = original["WAL"]
        assert original_wal_sheet.cell(row=4, column=1).value is None
    finally:
        original.close()


def test_historical_output_registry_requires_exposure_summary_path_when_wal_enabled(
    tmp_path: Path,
) -> None:
    """A config that enables "historical_wal_workbook" but leaves
    exposure_summary_xlsx unset must fail with a clear error, not a silent
    no-op or an obscure AttributeError deep in the WAL calculator."""
    all_programs_input = tmp_path / "all_programs.xlsx"
    ex_trend_input = tmp_path / "ex_trend.xlsx"
    trend_input = tmp_path / "trend.xlsx"
    monthly_pptx = tmp_path / "monthly.pptx"
    hist_all = tmp_path / "hist_all.xlsx"
    hist_ex = tmp_path / "hist_ex.xlsx"
    hist_trend = tmp_path / "hist_trend.xlsx"
    for file_path in (
        all_programs_input,
        ex_trend_input,
        trend_input,
        monthly_pptx,
        hist_all,
        hist_ex,
        hist_trend,
    ):
        file_path.write_bytes(b"placeholder")

    run_dir = tmp_path / "runs" / "2026-01-31"
    run_dir.mkdir(parents=True)
    config = WorkflowConfig(
        mosers_all_programs_xlsx=all_programs_input,
        mosers_ex_trend_xlsx=ex_trend_input,
        mosers_trend_xlsx=trend_input,
        hist_all_programs_3yr_xlsx=hist_all,
        hist_ex_llc_3yr_xlsx=hist_ex,
        hist_llc_3yr_xlsx=hist_trend,
        monthly_pptx=monthly_pptx,
        output_generators=(
            OutputGeneratorConfig(
                name="historical_workbook",
                registration="builtin:historical_workbook",
                stage="historical",
                enabled=False,
            ),
            OutputGeneratorConfig(
                name="historical_wal_workbook",
                registration="builtin:historical_wal_workbook",
                stage="historical",
            ),
        ),
    )

    with pytest.raises(ValueError, match="exposure_summary_xlsx"):
        run_module._update_historical_outputs(
            run_dir=run_dir,
            config=config,
            parsed_by_variant={
                "all_programs": {"cprs_ch": []},
                "ex_trend": {"cprs_ch": []},
                "trend": {"cprs_ch": []},
            },
            as_of_date=date(2026, 1, 31),
            warnings=[],
        )
