"""Tests that parser and writer steps apply name normalization."""

from __future__ import annotations

from counter_risk.parser import parse_exposure_row
from counter_risk.writer import build_exposure_record


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
