"""Tests that parser and writer steps apply name normalization."""

from __future__ import annotations

import pytest

import counter_risk.parsers.cprs_ch as _cprs_ch_module
import counter_risk.writers.historical_update as _historical_update_module
from counter_risk.parser import parse_exposure_row
from counter_risk.parsers.cprs_ch import _extract_text as _cprs_ch_extract_text
from counter_risk.parsers.cprs_ch import _matching_key as _cprs_ch_matching_key
from counter_risk.parsers.cprs_ch import _normalize_text as _cprs_ch_normalize_text
from counter_risk.parsers.cprs_fcm import _matching_key as _cprs_fcm_matching_key
from counter_risk.parsers.cprs_fcm import _normalize_text as _cprs_fcm_normalize_text
from counter_risk.parsers.exposure_maturity_schedule import (
    _normalize_text as _exposure_normalize_text,
)
from counter_risk.parsers.nisa import _matching_key as _nisa_matching_key
from counter_risk.parsers.nisa import _normalize_text as _nisa_normalize_text
from counter_risk.writer import build_exposure_record
from counter_risk.writers.historical_update import _normalize_header


def test_parser_applies_normalization() -> None:
    row = {
        "counterparty": "  Citigroup ",
        "clearing_house": " ICE   Clear   U.S. ",
        "program": "All Programs",
    }

    parsed = parse_exposure_row(row)

    assert parsed["counterparty"] == "Citibank"
    assert parsed["clearing_house"] == "ICE"


def test_writer_applies_normalization() -> None:
    record = build_exposure_record(
        counterparty=" Societe   Generale ",
        clearing_house=" Japan Securities Clearing Corporation ",
        exposure=42.0,
    )

    assert record["counterparty"] == "Soc Gen"
    assert record["clearing_house"] == "Japan SCC"
    assert record["exposure"] == 42.0


def test_parser_applies_canonicalization_to_unicode_punctuation() -> None:
    # Curly apostrophe variant must resolve to the same canonical mapping
    # as the ASCII-apostrophe spelling already covered by the registry.
    row = {
        "counterparty": "Goldman Sachs Int’l",
        "clearing_house": "ICE Clear U.S.",
        "program": "All Programs",
    }

    parsed = parse_exposure_row(row)

    assert parsed["counterparty"] == "Goldman Sachs"


# ---------------------------------------------------------------------------
# Workbook header matching (writers.historical_update._normalize_header)
# ---------------------------------------------------------------------------


def test_normalize_header_canonicalizes_unicode_punctuation() -> None:
    # Curly apostrophe and ASCII apostrophe must map to the same matching key.
    curly = _normalize_header("Goldman Sachs Int’l")
    ascii_ = _normalize_header("Goldman Sachs Int'l")
    assert curly == ascii_


def test_normalize_header_canonicalizes_dash_variants() -> None:
    # En-dash, em-dash, and unicode minus must collapse to ASCII hyphen.
    en_dash = _normalize_header("Korea Exchange–Seoul")
    em_dash = _normalize_header("Korea Exchange—Seoul")
    minus = _normalize_header("Korea Exchange−Seoul")
    ascii_ = _normalize_header("Korea Exchange-Seoul")
    assert en_dash == em_dash == minus == ascii_


def test_normalize_header_collapses_whitespace_and_casefolds() -> None:
    assert _normalize_header("  Total   x-clearing  ") == "total x-clearing"


def test_normalize_header_preserves_existing_none_handling() -> None:
    assert _normalize_header(None) == ""


# ---------------------------------------------------------------------------
# Parser display helpers preserve punctuation while matching keys canonicalize it
# ---------------------------------------------------------------------------


def test_parser_normalize_text_helpers_preserve_display_punctuation() -> None:
    assert _cprs_ch_normalize_text("Goldman Sachs Int’l") == "Goldman Sachs Int’l"
    assert _cprs_fcm_normalize_text("Korea Exchange–Seoul") == "Korea Exchange–Seoul"
    assert _nisa_normalize_text("Goldman Sachs Int’l") == "Goldman Sachs Int’l"


def test_parser_matching_key_helpers_canonicalize_unicode_punctuation() -> None:
    curly = "Goldman Sachs Int’l"
    ascii_ = "Goldman Sachs Int'l"

    assert _cprs_ch_matching_key(curly) == _cprs_ch_matching_key(ascii_)
    assert _cprs_fcm_matching_key(curly) == _cprs_fcm_matching_key(ascii_)
    assert _nisa_matching_key(curly) == _nisa_matching_key(ascii_)
    assert _exposure_normalize_text(curly) == _exposure_normalize_text(ascii_)

    en_dash = "Korea Exchange–Seoul"
    ascii_dash = "Korea Exchange-Seoul"
    assert _cprs_ch_matching_key(en_dash) == _cprs_ch_matching_key(ascii_dash)
    assert _cprs_fcm_matching_key(en_dash) == _cprs_fcm_matching_key(ascii_dash)
    assert _nisa_matching_key(en_dash) == _nisa_matching_key(ascii_dash)
    assert _exposure_normalize_text(en_dash) == _exposure_normalize_text(ascii_dash)


def test_parser_normalize_text_helpers_handle_none_and_whitespace() -> None:
    assert _cprs_ch_normalize_text(None) == ""
    assert _cprs_fcm_normalize_text(None) == ""
    assert _nisa_normalize_text(None) == ""
    assert _exposure_normalize_text(None) == ""

    assert _nisa_normalize_text("  Morgan   Stanley  ") == "Morgan Stanley"
    assert _exposure_normalize_text("\t Total  by  CP\n") == "Total by CP"


# ---------------------------------------------------------------------------
# Regression guards: matching paths must call canonicalize_name (AC3)
# ---------------------------------------------------------------------------


def test_normalize_header_calls_canonicalize_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """_normalize_header must route through canonicalize_name, not ad hoc logic."""
    calls: list[str] = []
    original = _historical_update_module.canonicalize_name

    def _spy(value: str) -> str:
        calls.append(value)
        return original(value)

    monkeypatch.setattr(_historical_update_module, "canonicalize_name", _spy)
    _normalize_header("Some Header")
    assert calls == ["Some Header"]


def test_cprs_ch_matching_key_calls_canonicalize_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """_matching_key must route through canonicalize_name, not ad hoc logic."""
    calls: list[str] = []
    original = _cprs_ch_module.canonicalize_name

    def _spy(value: str) -> str:
        calls.append(value)
        return original(value)

    monkeypatch.setattr(_cprs_ch_module, "canonicalize_name", _spy)
    _cprs_ch_matching_key("Test Name")
    assert calls  # canonicalize_name was called at least once


# ---------------------------------------------------------------------------
# Cross-path canonical key consistency (AC1)
# ---------------------------------------------------------------------------


def test_all_matching_paths_produce_same_key_for_dash_variants() -> None:
    """Parser, workbook, and registry paths resolve en-dash and ASCII dash identically."""
    from counter_risk.normalize import canonicalize_name

    en_dash_name = "Korea Exchange–Seoul"
    ascii_name = "Korea Exchange-Seoul"

    parser_key_en = _cprs_ch_matching_key(en_dash_name)
    parser_key_ascii = _cprs_ch_matching_key(ascii_name)
    workbook_key_en = _normalize_header(en_dash_name)
    workbook_key_ascii = _normalize_header(ascii_name)
    registry_key_en = canonicalize_name(en_dash_name)
    registry_key_ascii = canonicalize_name(ascii_name)

    assert parser_key_en == parser_key_ascii
    assert workbook_key_en == workbook_key_ascii
    assert registry_key_en == registry_key_ascii

    # All three paths must agree on the same canonical form
    assert parser_key_en == workbook_key_en
    assert workbook_key_en == registry_key_en.casefold()


def test_all_matching_paths_produce_same_key_for_apostrophe_variants() -> None:
    """Parser, workbook, and registry paths resolve curly and ASCII apostrophes identically."""
    from counter_risk.normalize import canonicalize_name

    curly = "Goldman Sachs Int’l"
    ascii_ = "Goldman Sachs Int'l"

    parser_key_curly = _cprs_ch_matching_key(curly)
    parser_key_ascii = _cprs_ch_matching_key(ascii_)
    workbook_key_curly = _normalize_header(curly)
    workbook_key_ascii = _normalize_header(ascii_)
    registry_key_curly = canonicalize_name(curly)
    registry_key_ascii = canonicalize_name(ascii_)

    assert parser_key_curly == parser_key_ascii
    assert workbook_key_curly == workbook_key_ascii
    assert registry_key_curly == registry_key_ascii
    assert workbook_key_curly == registry_key_curly.casefold()


# ---------------------------------------------------------------------------
# Display name preservation in user-facing parser output (AC2)
# ---------------------------------------------------------------------------


def test_cprs_ch_extract_text_preserves_unicode_apostrophe() -> None:
    """Parser output uses safe_display_name: Unicode apostrophe is preserved, not canonicalized."""
    curly = "Goldman Sachs Int’l"
    result = _cprs_ch_extract_text({1: curly}, 1)
    assert result == curly  # display name preserved
    assert result != "Goldman Sachs Int'l"  # canonical key would have ASCII apostrophe


def test_cprs_ch_extract_text_preserves_en_dash() -> None:
    """Parser output uses safe_display_name: en-dash is preserved, not collapsed to ASCII hyphen."""
    en_dash = "Korea Exchange–Seoul"
    result = _cprs_ch_extract_text({1: en_dash}, 1)
    assert result == en_dash  # display name preserved
    assert result != "Korea Exchange-Seoul"  # canonical key would have ASCII hyphen
