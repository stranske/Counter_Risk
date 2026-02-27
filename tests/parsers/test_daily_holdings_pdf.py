"""Tests for Daily Holdings PDF Repo Cash parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.parsers.daily_holdings_pdf import (
    expected_repo_counterparties,
    parse_daily_holdings_pdf,
)


@pytest.mark.parametrize(
    "fixture_name",
    ("daily_holdings_sample_1.pdf", "daily_holdings_sample_2.pdf"),
)
def test_parse_daily_holdings_pdf_fixture_totals_positive_and_key_counterparty_present(
    fixture_name: str,
) -> None:
    parsed = parse_daily_holdings_pdf(Path("tests/fixtures") / fixture_name)

    assert parsed
    assert sum(parsed.values()) > 0.0
    assert set(parsed).intersection(expected_repo_counterparties())


def test_parse_daily_holdings_pdf_maps_known_aliases_to_canonical_counterparties() -> None:
    parsed = parse_daily_holdings_pdf(Path("tests/fixtures/daily_holdings_sample_2.pdf"))

    assert "CIBC" in parsed
    assert "Buckler" in parsed
    assert "Daiwa" in parsed
