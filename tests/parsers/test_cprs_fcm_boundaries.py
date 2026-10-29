"""Small real workbooks exercise CPRS-FCM error and section boundaries."""

import pytest

from counter_risk.parsers import cprs_fcm as fcm


def _workbook(tmp_path, rows, sheet_name="CPRS - FCM"):
    path = tmp_path / "all-programs.xlsx"
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    for row in rows:
        sheet.append(row)
    workbook.save(path)
    workbook.close()
    return path


@pytest.mark.parametrize("parser", [fcm.parse_fcm_total_evidence, fcm.parse_futures_detail])
def test_missing_workbook_has_contextual_error(tmp_path, parser):
    with pytest.raises(FileNotFoundError, match="CPRS-FCM file not found"):
        parser(tmp_path / "missing.xlsx")


@pytest.mark.parametrize("parser", [fcm.parse_fcm_totals, fcm.parse_futures_detail])
@pytest.mark.parametrize("kind", ["zip", "worksheet"])
def test_malformed_workbook_reports_structure_error(tmp_path, parser, kind):
    path = _workbook(tmp_path, [], sheet_name="unrelated")
    if kind == "zip":
        path.write_bytes(b"invalid zip")
    with pytest.raises(ValueError, match="Malformed CPRS-FCM workbook structure") as caught:
        parser(path)
    assert caught.value.__cause__ is not None


@pytest.mark.parametrize("parser", [fcm.parse_fcm_totals, fcm.parse_futures_detail])
def test_absent_sections_return_typed_empty_frames(tmp_path, parser):
    path = _workbook(tmp_path, [["unrelated data"]])
    result = parser(path)
    assert result.empty
    assert result["Notional" if parser is fcm.parse_fcm_totals else "notional"].dtype == "float64"


def test_totals_section_requires_identifiable_counterparty_header(tmp_path):
    path = _workbook(tmp_path, [["Total by Counterparty/ FCM"], ["Bank", 20]])
    # The section marker itself contains the header words, so the resulting
    # incomplete column map must still fail before producing records.
    with pytest.raises(fcm.CprsFcmColumnsMissingError, match="Missing required columns"):
        fcm.parse_fcm_totals(path)


def test_futures_skips_blank_and_repeated_header_rows_and_reads_to_end(tmp_path):
    path = _workbook(
        tmp_path,
        [
            ["FUTURES DETAIL"],
            ["Account", "Description", "Class", "FCM", "Clearing House", "Notional", None],
            [None, None, "Equity"],
            ["Account", "Description", "Class", "FCM", "Clearing House", "Notional"],
            ["A1", "contract", "Equity", "Bank", "CME", 12.5],
        ],
    )
    records = fcm.parse_futures_detail(path).to_dict(orient="records")
    assert records == [
        {
            "account": "A1",
            "description": "contract",
            "class": "Equity",
            "fcm": "Bank",
            "clearing_house": "CME",
            "notional": 12.5,
        }
    ]


def test_futures_missing_columns_are_reported(tmp_path):
    path = _workbook(tmp_path, [["FUTURES DETAIL"], ["Account"], ["A1"]])
    with pytest.raises(
        fcm.CprsFcmColumnsMissingError, match="Missing required columns in FCM futures"
    ):
        fcm.parse_futures_detail(path)


def test_totals_skip_summary_and_empty_rows_and_read_to_end(tmp_path):
    path = _workbook(
        tmp_path,
        [
            [
                "Counterparty/ FCM",
                "TIPS",
                "Treasury",
                "Equity",
                "Commodity",
                "Currency",
                "Notional",
                "Notional change",
            ],
            [],
            ["Total by Counterparty/ FCM"],
            ["Total", 0, 0, 100, 0, 0, 100],
            ["Subtotal", 0, 0, 100, 0, 0, 100],
            [None, 0, 0, 100, 0, 0, 100],
            ["empty", 0, 0, 0, 0, 0, 0],
            ["Bank", 0, 0, 12.5, 0, 0, 12.5],
        ],
    )
    result = fcm.parse_fcm_totals(path)
    assert result["counterparty"].tolist() == ["Bank"]
    assert result["Notional"].tolist() == [12.5]
    assert fcm.parse_fcm_total_evidence(path)["Bank"] == {
        "counterparty": "Bank",
        "sheet": "CPRS - FCM",
        "row": 8,
        "method": "nisa_parser",
    }


def test_header_mapping_ignores_blank_and_duplicate_columns():
    headers = {
        1: "Account",
        2: "Description",
        3: "Class",
        4: "FCM",
        5: "Clearing House",
        6: "Notional",
        7: None,
        8: "Account",
    }
    assert fcm._build_futures_column_map({1: headers}, 1) == {
        "account": 1,
        "description": 2,
        "class": 3,
        "fcm": 4,
        "clearing_house": 5,
        "notional": 6,
    }
    assert fcm._find_totals_header_row({1: {1: "unrelated"}}) is None


def test_dataframe_fills_missing_fields_and_preserves_column_order():
    result = fcm._to_dataframe(
        records=[{"counterparty": "Bank"}],
        columns=("Notional", "counterparty", "description"),
        dtypes={"Notional": "float64", "counterparty": "string", "description": "string"},
    )
    assert result.to_dict(orient="records") == [
        {"Notional": 0.0, "counterparty": "Bank", "description": ""}
    ]
