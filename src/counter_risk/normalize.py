"""Deterministic name normalization helpers for Counter Risk entities.

This module centralizes spreadsheet/header name cleanup so parser and writer
steps resolve to stable canonical labels.
"""

from __future__ import annotations


def _normalize_whitespace(name: str) -> str:
    """Trim leading/trailing whitespace and collapse internal runs of whitespace."""

    return " ".join(name.split())


def normalize_counterparty(name: str) -> str:
    """Normalize a counterparty name to the canonical historical workbook label."""

    mappings = {
        "Citigroup": "Citibank",
        "Bank of America, NA": "Bank of America",
        "Bank of America NA": "Bank of America",
        "Goldman Sachs Int'l": "Goldman Sachs",
        "Societe Generale": "Soc Gen",
        "Barclays Bank PLC": "Barclays",
    }
    normalized = _normalize_whitespace(name)
    return mappings.get(normalized, normalized)


def normalize_clearing_house(name: str) -> str:
    """Normalize a clearing house name to the canonical historical workbook label."""

    mappings = {
        "CME Clearing House": "CME",
        "ICE Clear U.S.": "ICE",
        "ICE Clear US": "ICE",
        "ICE Clear Europe": "ICE Euro",
        "EUREX Clearing": "EUREX",
        "Japan Securities Clearing Corporation": "Japan SCC",
        "Korea Exchange (in-house)": "Korea Exchange",
    }
    normalized = _normalize_whitespace(name)
    return mappings.get(normalized, normalized)
