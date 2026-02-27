"""Tests for the All Programs raw NISA input structure contract."""

from __future__ import annotations

from pathlib import Path

from counter_risk.parsers.nisa_all_programs import (
    get_nisa_all_programs_input_structure,
    parse_nisa_all_programs,
)


def test_all_programs_input_structure_defines_required_fields() -> None:
    structure = get_nisa_all_programs_input_structure()

    assert structure.required_headers == (
        "cash",
        "tips",
        "treasury",
        "equity",
        "commodity",
        "currency",
        "notional",
        "notional_change",
        "annualized_volatility",
    )
    assert "counterparty" in structure.header_aliases
    assert "counterparty/clearing house" in structure.header_aliases["counterparty"]
    assert structure.totals_marker == "total by counterparty/clearing house"
    assert structure.totals_stop_markers == (
        "total current exposure",
        "mosers program",
        "notional breakdown",
    )
    assert structure.segment_aliases["swaps"] == "swaps"
    assert structure.segment_aliases["repo"] == "repo"
    assert structure.segment_aliases["futures / cdx"] == "futures_cdx"


def test_all_programs_fixture_parses_with_documented_structure() -> None:
    structure = get_nisa_all_programs_input_structure()
    parsed = parse_nisa_all_programs(Path("tests/fixtures/NISA Monthly All Programs - Raw.xlsx"))

    assert parsed.ch_rows
    assert parsed.totals_rows
    assert len(structure.required_headers) == 9
