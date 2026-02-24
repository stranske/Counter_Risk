"""Focused sheet-keying tests for parsed reconciliation payloads."""

from __future__ import annotations

import counter_risk.pipeline.run as run_module


def test_build_parsed_data_by_sheet_keys_exact_sheet_names() -> None:
    workbook_sheet_names = ["Sheet A", "Sheet B"]
    result = run_module._build_parsed_data_by_sheet(
        parsed_sections={
            "totals": [{"counterparty": "Counterparty A", "Notional": 10.0}],
            "futures": [],
        },
        historical_series_headers_by_sheet={
            sheet_name: ("Counterparty A",) if sheet_name == "Sheet A" else ()
            for sheet_name in workbook_sheet_names
        },
    )

    assert set(result.keys()) == set(workbook_sheet_names)
    assert result["Sheet B"]["totals"] == []
    assert result["Sheet B"]["futures"] == []


def test_build_parsed_data_by_sheet_multi_sheet_row_partition() -> None:
    result = run_module._build_parsed_data_by_sheet(
        parsed_sections={
            "totals": [
                {"counterparty": "Counterparty A", "Notional": 10.0},
                {"counterparty": "Counterparty B", "Notional": 20.0},
            ],
            "futures": [
                {"clearing_house": "Clearing A", "notional": 3.0},
                {"clearing_house": "Clearing B", "notional": 4.0},
            ],
        },
        historical_series_headers_by_sheet={
            "Sheet A": ("Counterparty A", "Clearing A"),
            "Sheet B": ("Counterparty B", "Clearing B"),
        },
    )

    assert [row["counterparty"] for row in result["Sheet A"]["totals"]] == ["Counterparty A"]
    assert [row["counterparty"] for row in result["Sheet B"]["totals"]] == ["Counterparty B"]
    assert [row["clearing_house"] for row in result["Sheet A"]["futures"]] == ["Clearing A"]
    assert [row["clearing_house"] for row in result["Sheet B"]["futures"]] == ["Clearing B"]


def test_build_parsed_data_by_sheet_uses_actual_workbook_sheet_names_as_keys() -> None:
    parsed_data_by_sheet = run_module._build_parsed_data_by_sheet(
        parsed_sections={
            "totals": [
                {"counterparty": "Counterparty A", "Notional": 10.0},
                {"counterparty": "Counterparty B", "Notional": 20.0},
            ],
            "futures": [{"clearing_house": "Clearing B", "notional": 5.0}],
        },
        historical_series_headers_by_sheet={
            "Sheet A": ("Counterparty A",),
            "Sheet B": ("Counterparty B", "Clearing B"),
        },
    )

    assert set(parsed_data_by_sheet) == {"Sheet A", "Sheet B"}


def test_build_parsed_data_by_sheet_includes_total_only_when_total_sheet_exists() -> None:
    without_total = run_module._build_parsed_data_by_sheet(
        parsed_sections={"totals": [{"counterparty": "Counterparty A"}], "futures": []},
        historical_series_headers_by_sheet={"Sheet A": ("Counterparty A",)},
    )

    assert set(without_total) == {"Sheet A"}
    assert "Total" not in without_total

    with_total = run_module._build_parsed_data_by_sheet(
        parsed_sections={
            "totals": [
                {"counterparty": "Counterparty A"},
                {"counterparty": "Counterparty B"},
            ],
            "futures": [],
        },
        historical_series_headers_by_sheet={
            "Sheet A": ("Counterparty A",),
            "Total": ("Counterparty B",),
        },
    )

    assert set(with_total) == {"Sheet A", "Total"}
    assert [row["counterparty"] for row in with_total["Sheet A"]["totals"]] == ["Counterparty A"]
    assert [row["counterparty"] for row in with_total["Total"]["totals"]] == ["Counterparty B"]


def test_build_parsed_data_by_sheet_uses_per_sheet_historical_header_variants() -> None:
    parsed_data_by_sheet = run_module._build_parsed_data_by_sheet(
        parsed_sections={
            "totals": [{"counterparty": "Bank of America, NA", "Notional": 100.0}],
            "futures": [{"clearing_house": "ICE Clear Europe", "notional": 50.0}],
        },
        historical_series_headers_by_sheet={
            "Legacy Counterparties": ("Bank of America",),
            "CPRS - CH": ("ICE Euro",),
        },
    )

    assert set(parsed_data_by_sheet) == {"Legacy Counterparties", "CPRS - CH"}
    assert [
        row["counterparty"] for row in parsed_data_by_sheet["Legacy Counterparties"]["totals"]
    ] == ["Bank of America, NA"]
    assert [row["clearing_house"] for row in parsed_data_by_sheet["CPRS - CH"]["futures"]] == [
        "ICE Clear Europe"
    ]
