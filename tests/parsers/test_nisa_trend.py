"""Tests for raw NISA Trend parser."""

from __future__ import annotations

from pathlib import Path

from counter_risk.parsers.nisa_trend import parse_nisa_trend


def test_parse_nisa_trend_fixture_without_errors() -> None:
    parsed = parse_nisa_trend(Path("tests/fixtures/NISA Monthly Trend - Raw.xlsx"))

    assert parsed.ch_rows
    assert parsed.totals_rows
    assert {row.segment for row in parsed.ch_rows} == {"swaps", "repo", "futures_cdx"}
