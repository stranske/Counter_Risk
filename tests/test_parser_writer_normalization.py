"""Tests that parser and writer steps apply name normalization."""

from __future__ import annotations

from counter_risk.parser import parse_exposure_row
from counter_risk.parsers.cprs_ch import _normalize_text as _cprs_ch_normalize_text
from counter_risk.parsers.cprs_fcm import _normalize_text as _cprs_fcm_normalize_text
from counter_risk.parsers.exposure_maturity_schedule import (
    _normalize_text as _exposure_normalize_text,
)
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
# Parser matching-key helpers route through canonicalize_name
# ---------------------------------------------------------------------------


def test_parser_normalize_text_helpers_canonicalize_unicode_punctuation() -> None:
    # All parser matching-key helpers must resolve apostrophe and dash variants
    # to the same canonical key as their ASCII spelling.
    curly = "Goldman Sachs Int’l"
    ascii_ = "Goldman Sachs Int'l"

    assert _cprs_ch_normalize_text(curly) == _cprs_ch_normalize_text(ascii_)
    assert _cprs_fcm_normalize_text(curly) == _cprs_fcm_normalize_text(ascii_)
    assert _nisa_normalize_text(curly) == _nisa_normalize_text(ascii_)
    assert _exposure_normalize_text(curly) == _exposure_normalize_text(ascii_)

    en_dash = "Korea Exchange–Seoul"
    ascii_dash = "Korea Exchange-Seoul"
    assert _cprs_ch_normalize_text(en_dash) == _cprs_ch_normalize_text(ascii_dash)
    assert _cprs_fcm_normalize_text(en_dash) == _cprs_fcm_normalize_text(ascii_dash)
    assert _nisa_normalize_text(en_dash) == _nisa_normalize_text(ascii_dash)
    assert _exposure_normalize_text(en_dash) == _exposure_normalize_text(ascii_dash)


def test_parser_normalize_text_helpers_handle_none_and_whitespace() -> None:
    assert _cprs_ch_normalize_text(None) == ""
    assert _cprs_fcm_normalize_text(None) == ""
    assert _nisa_normalize_text(None) == ""
    assert _exposure_normalize_text(None) == ""

    assert _nisa_normalize_text("  Morgan   Stanley  ") == "Morgan Stanley"
    assert _exposure_normalize_text("\t Total  by  CP\n") == "Total by CP"
