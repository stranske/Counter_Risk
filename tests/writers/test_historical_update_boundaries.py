"""Historical workbook failures and preservation contracts using small workbooks."""

from datetime import date, datetime
from pathlib import Path

import pytest

from counter_risk.writers import historical_update as history


def test_locate_uses_default_root_and_legacy_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "_resolve_repo_root", lambda: tmp_path)
    legacy = tmp_path / history._LEGACY_EX_LLC_3_YEAR_RELATIVE_PATH
    legacy.parent.mkdir(parents=True)
    legacy.touch()
    assert history.locate_ex_llc_3_year_workbook() == legacy
    preferred = tmp_path / history._DEFAULT_EX_LLC_3_YEAR_RELATIVE_PATH
    preferred.parent.mkdir(parents=True)
    preferred.touch()
    assert history.locate_ex_llc_3_year_workbook(search_root=str(tmp_path)) == preferred


def test_validate_rejects_directory_with_xlsx_suffix(tmp_path):
    directory = tmp_path / "directory.xlsx"
    directory.mkdir()
    with pytest.raises(history.WorkbookValidationError, match="must point to a file"):
        history._validate_workbook_path(directory)


@pytest.mark.parametrize("operation", ["open", "append"])
def test_corrupt_workbook_load_is_reported_with_cause(tmp_path, operation):
    path = tmp_path / "broken.xlsx"
    path.write_bytes(b"invalid workbook")
    with pytest.raises(history.WorkbookValidationError, match="Unable to load workbook") as caught:
        if operation == "open":
            history.open_ex_llc_3_year_workbook(
                search_root=tmp_path, expected_relative_path=Path(path.name)
            )
        else:
            history.append_row_all_programs(path, {}, append_date=date(2026, 1, 31))
    assert caught.value.__cause__ is not None
    assert path.read_bytes() == b"invalid workbook"


@pytest.mark.parametrize("label", [None, "  "])
def test_empty_series_labels_are_ignored(label):
    assert history._normalize_series_key(label) == ""


def test_rollup_coercion_ignores_blank_labels():
    assert history._coerce_rollup_data({" ": "not numeric", "Total": "12.5"}) == {"total": 12.5}


def test_read_only_cell_lookup_does_not_materialize_missing_cells(tmp_path):
    path = tmp_path / "read-only.xlsx"
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    workbook.active["B2"] = "Date"
    workbook.save(path)
    workbook.close()
    loaded = openpyxl.load_workbook(path, read_only=True)
    try:
        sheet = loaded.active
        assert history._get_cell_value_no_create(sheet, row=2, column=2) == "Date"
        assert history._get_cell_value_no_create(sheet, row=10, column=2) is None
    finally:
        loaded.close()


@pytest.mark.parametrize("value", [datetime(2026, 1, 31, 15, 30), "  "])
def test_cell_dates_support_datetime_and_blank_text(value):
    expected = value.date() if isinstance(value, datetime) else None
    assert history._coerce_cell_date(value) == expected


def test_inferred_date_skips_blank_candidate_then_uses_later_header():
    assert history._infer_date_from_cprs_ch_header(
        {"Report Date": None, "As of Date": "01/31/2026"}
    ) == date(2026, 1, 31)
    assert history._infer_date_from_cprs_ch_header({"Report Date": None}) is None


@pytest.mark.parametrize(
    "resolver", [history._get_date_column, history._get_date_column_from_consolidated]
)
def test_date_column_resolvers_reject_missing_header(resolver):
    with pytest.raises(history.WorkbookValidationError, match="missing a date column"):
        resolver({})


def test_header_scan_reports_missing_date_label():
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet["A1"] = "Counterparty"
    with pytest.raises(history.WorkbookValidationError, match="Unable to locate a header row"):
        history._find_header_row(sheet)
    workbook.close()


def test_wal_column_accepts_prefixed_label_and_rejects_absence():
    assert (
        history._get_wal_column_from_consolidated({1: "date", 3: "wal years"}, date_column=1) == 3
    )
    with pytest.raises(history.WorkbookValidationError, match="missing a WAL value column"):
        history._get_wal_column_from_consolidated({1: "date", 2: "Total"}, date_column=1)


@pytest.mark.parametrize("operation", ["wal", "counterparty"])
def test_append_rejects_missing_worksheet(operation):
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    try:
        with pytest.raises(history.WorksheetNotFoundError, match="Required worksheet not found"):
            if operation == "wal":
                history.read_wal_sheet_append_location(workbook)
            else:
                history._append_to_sheet(
                    workbook=workbook,
                    sheet_name="missing",
                    rollup_data={},
                    resolved_date=date(2026, 1, 31),
                )
    finally:
        workbook.close()


@pytest.mark.parametrize(
    ("old_value", "new_value", "old_format", "new_format", "message"),
    [
        ("=A2", 2, "General", "General", "formula usage"),
        (2, 3, "General", "General", "cell value"),
        (2, 2, "0.00", "0%", "number format"),
    ],
)
def test_preserved_wal_cells_detect_changes(old_value, new_value, old_format, new_format, message):
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet["A1"] = old_value
    sheet["A1"].number_format = old_format
    snapshots = history._snapshot_preserved_wal_cells(
        sheet, preserve_through_row=1, preserve_through_column=1
    )
    sheet["A1"] = new_value
    sheet["A1"].number_format = new_format
    with pytest.raises(history.WorkbookValidationError, match=message):
        history._validate_preserved_wal_cells(sheet, snapshots)
    workbook.close()


def test_date_only_sheet_appends_and_reports_missing_numeric_series(caplog):
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "history"
    sheet["A1"] = "Date"
    history._append_to_sheet(
        workbook=workbook, sheet_name="history", rollup_data={}, resolved_date=date(2026, 1, 31)
    )
    assert sheet["A2"].value == date(2026, 1, 31)
    assert "No numeric series columns detected in history" in caplog.text
    workbook.close()


def test_wal_initial_observation_is_written_below_header(tmp_path):
    path = tmp_path / "wal.xlsx"
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "WAL"
    sheet.append(["Date", "WAL"])
    workbook.save(path)
    workbook.close()
    history.append_wal_row(path, px_date=date(2026, 1, 31), wal_value=2.5)
    loaded = openpyxl.load_workbook(path)
    try:
        assert loaded["WAL"]["A2"].value == datetime(2026, 1, 31)
        assert loaded["WAL"]["B2"].value == 2.5
    finally:
        loaded.close()


def test_append_ignores_empty_header_columns():
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "history"
    sheet.append(["Date", None, "Total"])
    history._append_to_sheet(
        workbook=workbook,
        sheet_name="history",
        rollup_data={"Total": 12.5},
        resolved_date=date(2026, 1, 31),
    )
    assert sheet["A2"].value == date(2026, 1, 31)
    assert sheet["B2"].value is None
    assert sheet["C2"].value == 12.5
    workbook.close()


def test_append_date_resolution_requires_a_source():
    with pytest.raises(history.AppendDateResolutionError, match="Unable to resolve append date"):
        history._resolve_append_date(append_date=None, config_as_of_date=None)


@pytest.mark.parametrize("value", ["yesterday", 123])
def test_cell_date_rejects_unrecognized_values(value):
    with pytest.raises(history.AppendDateError, match="Unable to parse existing worksheet date"):
        history._coerce_cell_date(value)


def test_wal_rolling_window_removes_oldest_observations():
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["Date", "WAL"])
    for month in range(1, 6):
        sheet.append([date(2026, month, 1), month / 2])
    history._trim_wal_sheet_to_rolling_window(sheet, header_row=1, date_column=1, window_months=3)
    assert list(sheet.values) == [
        ("Date", "WAL"),
        (date(2026, 3, 1), 1.5),
        (date(2026, 4, 1), 2.0),
        (date(2026, 5, 1), 2.5),
    ]
    workbook.close()
