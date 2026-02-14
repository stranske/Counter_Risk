"""Tests for raw NISA All Programs parser."""

from __future__ import annotations

from pathlib import Path

from counter_risk.parsers.nisa_all_programs import parse_nisa_all_programs


def test_parse_nisa_all_programs_fixture_without_errors() -> None:
    parsed = parse_nisa_all_programs(Path("tests/fixtures/NISA Monthly All Programs - Raw.xlsx"))

    assert parsed.ch_rows
    assert parsed.totals_rows
    assert {row.segment for row in parsed.ch_rows} == {"swaps", "repo", "futures_cdx"}
