"""Unit tests for counterparty and clearing house normalization."""

from __future__ import annotations

import pytest

from counter_risk.normalize import (
    canonicalize_name,
    normalize_clearing_house,
    normalize_counterparty,
    safe_display_name,
)


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


# ---------------------------------------------------------------------------
# canonicalize_name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw_name", "expected"),
    [
        # Leading/trailing whitespace stripped
        ("  Morgan Stanley  ", "Morgan Stanley"),
        # Internal whitespace collapsed
        ("Morgan  Stanley", "Morgan Stanley"),
        # Mixed leading, trailing, and internal
        ("  Goldman   Sachs  ", "Goldman Sachs"),
        # Tabs and newlines treated as whitespace
        ("Barclays\tBank\nPLC", "Barclays Bank PLC"),
        # Curly right apostrophe → ASCII apostrophe
        ("Goldman Sachs Int\u2019l", "Goldman Sachs Int'l"),
        # Curly left apostrophe → ASCII apostrophe
        ("Goldman Sachs Int\u2018l", "Goldman Sachs Int'l"),
        # Backtick → ASCII apostrophe
        ("Goldman Sachs Int`l", "Goldman Sachs Int'l"),
        # En-dash → hyphen-minus
        ("Korea Exchange\u2013Seoul", "Korea Exchange-Seoul"),
        # Em-dash → hyphen-minus
        ("Korea Exchange\u2014Seoul", "Korea Exchange-Seoul"),
        # Minus sign → hyphen-minus
        ("Korea Exchange\u2212Seoul", "Korea Exchange-Seoul"),
        # Already canonical: no change
        ("Citibank", "Citibank"),
        # Empty string stays empty
        ("", ""),
        # Only whitespace → empty
        ("   ", ""),
    ],
)
def test_canonicalize_name(raw_name: str, expected: str) -> None:
    assert canonicalize_name(raw_name) == expected


def test_canonicalize_name_preserves_case() -> None:
    assert canonicalize_name("  BANK of america  ") == "BANK of america"


def test_canonicalize_name_normalizes_apostrophe_before_mapping() -> None:
    # Curly-apostrophe variant of "Goldman Sachs Int'l" should map correctly
    # after canonicalization feeds into normalize_counterparty
    curly = "Goldman Sachs Int\u2019l"
    assert normalize_counterparty(curly) == "Goldman Sachs"


def test_canonicalize_name_hyphen_preserved_in_known_name() -> None:
    # Hyphens that are already ASCII hyphen-minus must be unchanged
    assert canonicalize_name("Korea Exchange-Seoul") == "Korea Exchange-Seoul"


# ---------------------------------------------------------------------------
# safe_display_name
# ---------------------------------------------------------------------------


def test_safe_display_name_collapses_whitespace() -> None:
    # Leading/trailing whitespace removed, internal runs collapsed
    assert safe_display_name("  Morgan  Stanley  ") == "Morgan Stanley"


def test_safe_display_name_preserves_case() -> None:
    assert safe_display_name("  ICE CLEAR europe  ") == "ICE CLEAR europe"


def test_safe_display_name_preserves_unicode_apostrophe() -> None:
    # Curly apostrophe is kept intact – it is a legitimate display character
    curly = "Goldman Sachs Int\u2019l"
    assert safe_display_name(curly) == curly


def test_safe_display_name_preserves_en_dash() -> None:
    # En-dash is kept intact for display; only whitespace is cleaned
    en_dash = "Korea Exchange\u2013Seoul"
    assert safe_display_name(en_dash) == en_dash


def test_safe_display_name_differs_from_canonicalize_name_on_unicode_punctuation() -> None:
    # canonicalize_name (the matching key) normalises Unicode punctuation;
    # safe_display_name intentionally does not.
    curly_input = "Goldman Sachs Int\u2019l"
    assert canonicalize_name(curly_input) == "Goldman Sachs Int'l"
    assert safe_display_name(curly_input) == curly_input  # unchanged

    en_dash_input = "Korea Exchange\u2013Seoul"
    assert canonicalize_name(en_dash_input) == "Korea Exchange-Seoul"
    assert safe_display_name(en_dash_input) == en_dash_input  # unchanged


def test_safe_display_name_empty_string() -> None:
    assert safe_display_name("") == ""


def test_safe_display_name_only_whitespace() -> None:
    assert safe_display_name("   ") == ""
