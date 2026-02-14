"""Tests for MOSERS workbook generation from raw NISA input."""

from __future__ import annotations

from pathlib import Path

from counter_risk.parsers import parse_cprs_ch, parse_fcm_totals, parse_futures_detail
from counter_risk.writers.mosers_workbook import generate_mosers_workbook


def test_generate_mosers_workbook_creates_new_file_with_required_sheets(tmp_path: Path) -> None:
    destination = tmp_path / "MOSERS Generated - All Programs.xlsx"
    output_path = generate_mosers_workbook(
        raw_nisa_path=Path("tests/fixtures/NISA Monthly All Programs - Raw.xlsx"),
        output_path=destination,
    )

    assert output_path == destination
    assert output_path.exists()

    from openpyxl import load_workbook  # type: ignore[import-untyped]

    workbook = load_workbook(output_path, read_only=True, data_only=True)
    try:
        assert workbook.sheetnames == ["CPRS - CH", "CPRS - FCM"]
    finally:
        workbook.close()


def test_generate_mosers_workbook_output_is_parseable_by_existing_milestone_one_parsers(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "MOSERS Generated - All Programs.xlsx"
    output_path = generate_mosers_workbook(
        raw_nisa_path=Path("tests/fixtures/NISA Monthly All Programs - Raw.xlsx"),
        output_path=destination,
    )

    ch_df = parse_cprs_ch(output_path)
    totals_df = parse_fcm_totals(output_path)
    futures_df = parse_futures_detail(output_path)

    assert not ch_df.empty
    assert not totals_df.empty
    assert tuple(totals_df.columns) == (
        "counterparty",
        "TIPS",
        "Treasury",
        "Equity",
        "Commodity",
        "Currency",
        "Notional",
        "NotionalChange",
    )
    assert tuple(futures_df.columns) == (
        "account",
        "description",
        "class",
        "fcm",
        "clearing_house",
        "notional",
    )
