"""CPRS-CH structure failures and published class-breakdown selection."""

import pytest

from counter_risk.parsers import cprs_ch as ch

HEADERS = [
    None,
    "Counterparty",
    "Cash",
    "TIPS",
    "Treasury",
    "Equity",
    "Commodity",
    "Currency",
    "Notional",
]


def _workbook(tmp_path, rows, *, name="trend.xlsx", sheet_name="CPRS - CH"):
    path = tmp_path / name
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    for row in rows:
        sheet.append(row)
    workbook.save(path)
    workbook.close()
    return path


@pytest.mark.parametrize("kind", ["zip", "worksheet"])
def test_parser_reports_malformed_workbook(tmp_path, kind):
    path = _workbook(tmp_path, [], sheet_name="unrelated")
    if kind == "zip":
        path.write_bytes(b"invalid zip")
    with pytest.raises(ValueError, match="Malformed CPRS-CH workbook structure") as caught:
        ch.parse_cprs_ch(path)
    assert caught.value.__cause__ is not None


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ([["unrelated"]], "Unable to locate CPRS-CH header row"),
        (
            [["Counterparty", "Notional Change From Prior Month"], []],
            "missing required column: Notional",
        ),
        ([HEADERS, []], "No CPRS-CH segments detected"),
        ([HEADERS, [], ["Futures"]], "CPRS-CH parser produced no rows"),
    ],
)
def test_parser_rejects_incomplete_structure(tmp_path, rows, message):
    with pytest.raises(ValueError, match=message):
        ch.parse_cprs_ch(_workbook(tmp_path, rows))


def test_numeric_headers_allow_missing_counterparty_label(tmp_path):
    headers = list(HEADERS)
    headers[1] = None
    path = _workbook(tmp_path, [headers, [], ["Futures", "CME", 0, 0, 0, 15, 0, 0, 15]])
    parsed = ch.parse_cprs_ch(path)
    assert parsed["Counterparty"].tolist() == ["CME"]
    assert parsed["Notional"].tolist() == [15.0]


def test_trend_swaps_relabel_preserves_totals_segment(tmp_path):
    path = _workbook(
        tmp_path,
        [
            HEADERS,
            [],
            ["Swaps", "CME", 0, 0, 0, 15, 0, 0, 15],
            ["Total by Counterparty/Clearing House", "CME", 0, 0, 0, 15, 0, 0, 15],
        ],
    )
    parsed = ch.parse_cprs_ch(path)
    assert parsed["Segment"].tolist() == ["futures", "totals"]
    assert parsed["SourceRow"].tolist() == [3, 4]


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("bad", "Invalid non-numeric value"),
        (float("inf"), "Invalid non-finite numeric value"),
        (1e16, "Out-of-range numeric value"),
    ],
)
def test_numeric_validation_reports_field_and_source_row(value, message):
    record = dict.fromkeys(
        ("Cash", "TIPS", "Treasury", "Equity", "Commodity", "Currency", "Notional"), 0.0
    )
    record["Notional"] = value
    with pytest.raises(ValueError, match=f"{message} for Notional at row 42"):
        ch._validate_numeric_ranges(record, 42)


def test_class_breakdown_requires_existing_workbook(tmp_path):
    with pytest.raises(FileNotFoundError, match="CPRS-CH file not found"):
        ch.read_class_notional_breakdown(tmp_path / "missing.xlsx")


@pytest.mark.parametrize("kind", ["zip", "header", "classes", "breakdown"])
def test_class_breakdown_returns_none_when_unavailable(tmp_path, kind):
    rows = {
        "zip": [],
        "header": [["unrelated"]],
        "classes": [["Counterparty", "Notional"], [], ["Notional Breakdown", 100]],
        "breakdown": [HEADERS, [], ["Futures", "CME", 0, 0, 0, 15, 0, 0, 15]],
    }[kind]
    path = _workbook(tmp_path, rows)
    if kind == "zip":
        path.write_bytes(b"invalid zip")
    assert ch.read_class_notional_breakdown(path) is None


@pytest.mark.parametrize("absolute", [False, True])
def test_class_breakdown_prefers_first_absolute_row_and_parses_percentages(tmp_path, absolute):
    rows = [HEADERS, [], ["Notional Breakdown", None, None, "10%", "20%", "30%", "15%", "25%"]]
    if absolute:
        rows.extend(
            [
                [
                    "Notional Breakdown (Absolute Values)",
                    None,
                    None,
                    "5%",
                    "25%",
                    "40%",
                    "10%",
                    "20%",
                ],
                ["Notional Breakdown (Absolute Values)", None, None, 99, 99, 99, 99, 99],
            ]
        )
    rows.append(["Notional Breakdown", None, None, 99, 99, 99, 99, 99])
    result = ch.read_class_notional_breakdown(_workbook(tmp_path, rows))
    expected = [5.0, 25.0, 40.0, 10.0, 20.0] if absolute else [10.0, 20.0, 30.0, 15.0, 25.0]
    assert result == dict(
        zip(("TIPS", "Treasury", "Equity", "Commodity", "Currency"), expected, strict=True)
    )


def test_class_breakdown_defaults_missing_and_invalid_cells_to_zero(tmp_path):
    path = _workbook(
        tmp_path,
        [HEADERS, [], ["Notional Breakdown", None, None, "invalid", None, "", "(12.5%)", "25%"]],
    )
    assert ch.read_class_notional_breakdown(path) == {
        "TIPS": 0.0,
        "Treasury": 0.0,
        "Equity": 0.0,
        "Commodity": -12.5,
        "Currency": 25.0,
    }
