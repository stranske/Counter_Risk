"""Tests for raw NISA All Programs parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.parsers.nisa_all_programs import parse_nisa_all_programs

_RAW_NISA_FIXTURE = Path("tests/fixtures/NISA Monthly All Programs - Raw.xlsx")


def test_parse_nisa_all_programs_fixture_without_errors() -> None:
    parsed = parse_nisa_all_programs(_RAW_NISA_FIXTURE)

    assert parsed.ch_rows
    assert parsed.totals_rows
    assert {row.segment for row in parsed.ch_rows} == {"swaps", "repo", "futures_cdx"}


def test_parse_nisa_all_programs_fixture_has_expected_deterministic_structure() -> None:
    parsed = parse_nisa_all_programs(_RAW_NISA_FIXTURE)

    assert len(parsed.ch_rows) == 25
    assert len(parsed.totals_rows) == 16

    first_swap = parsed.ch_rows[0]
    assert first_swap.segment == "swaps"
    assert first_swap.counterparty == "Citigroup"
    assert first_swap.notional == pytest.approx(-8187360.202)
    assert first_swap.annualized_volatility == pytest.approx(0.1540076984990998)

    first_repo = next(row for row in parsed.ch_rows if row.segment == "repo")
    assert first_repo.counterparty == "Morgan Stanley"
    assert first_repo.notional == pytest.approx(66377883.11)

    first_futures_cdx = next(row for row in parsed.ch_rows if row.segment == "futures_cdx")
    assert first_futures_cdx.counterparty == "CME"
    assert first_futures_cdx.notional_change == pytest.approx(34510685.43000001)

    first_total = parsed.totals_rows[0]
    assert first_total.counterparty == "Citibank"
    assert first_total.notional == pytest.approx(-8187360.202)

    jp_morgan_total = next(row for row in parsed.totals_rows if row.counterparty == "JP Morgan")
    assert jp_morgan_total.notional == pytest.approx(1648697237.1460001)
    assert jp_morgan_total.notional_change == pytest.approx(-227816480.2758999)
