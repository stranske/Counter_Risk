"""Unit tests for counterparty and clearing house normalization."""

from __future__ import annotations

import pytest

from counter_risk.normalize import normalize_clearing_house, normalize_counterparty


@pytest.mark.parametrize(
    ("raw_name", "expected"),
    [
        ("Citigroup", "Citibank"),
        ("Bank of America, NA", "Bank of America"),
        ("Goldman Sachs Int'l", "Goldman Sachs"),
        ("Societe Generale", "Soc Gen"),
        ("Barclays Bank PLC", "Barclays"),
    ],
)
def test_normalize_counterparty_mappings(raw_name: str, expected: str) -> None:
    assert normalize_counterparty(raw_name) == expected


@pytest.mark.parametrize(
    ("raw_name", "expected"),
    [
        ("CME Clearing House", "CME"),
        ("ICE Clear U.S.", "ICE"),
        ("ICE Clear Europe", "ICE Euro"),
        ("EUREX Clearing", "EUREX"),
        ("Japan Securities Clearing Corporation", "Japan SCC"),
        ("Korea Exchange (in-house)", "Korea Exchange"),
    ],
)
def test_normalize_clearing_house_mappings(raw_name: str, expected: str) -> None:
    assert normalize_clearing_house(raw_name) == expected


def test_normalize_counterparty_cleans_whitespace() -> None:
    assert normalize_counterparty("   Societe   Generale   ") == "Soc Gen"


def test_normalize_clearing_house_cleans_whitespace() -> None:
    assert normalize_clearing_house("  ICE   Clear   U.S.  ") == "ICE"


def test_normalize_counterparty_unknown_name_is_noop() -> None:
    assert normalize_counterparty("Morgan Stanley") == "Morgan Stanley"


def test_normalize_clearing_house_unknown_name_is_noop() -> None:
    assert normalize_clearing_house("LCH") == "LCH"
