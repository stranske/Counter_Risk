"""Deterministic name normalization helpers for Counter Risk entities.

This module centralizes spreadsheet/header name cleanup so parser and writer
steps resolve to stable canonical labels.

Public API
----------
canonicalize_name   - Low-level text canonicalization (whitespace + punctuation).
safe_display_name   - Human-readable form of a canonicalized name.
normalize_counterparty   - Map a counterparty raw name to its workbook label.
normalize_clearing_house - Map a clearing house raw name to its workbook label.
"""

from __future__ import annotations

import re

# Apostrophe variants → ASCII apostrophe
_APOSTROPHE_RE = re.compile(r"[\u2018\u2019\u201b\u02bc`]")

# Hyphen/dash variants → ASCII hyphen-minus
_DASH_RE = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]")


def canonicalize_name(name: str) -> str:
    """Return a deterministic canonical form of *name*.

    Transformations applied (in order):
    1. Normalize apostrophe variants (curly quotes, backtick) to ``'``.
    2. Normalize dash/hyphen variants (en-dash, em-dash, etc.) to ``-``.
    3. Strip leading/trailing whitespace and collapse internal whitespace runs.

    The result preserves the original letter case.  Use
    :func:`safe_display_name` when you need a human-readable label or
    :func:`normalize_counterparty` / :func:`normalize_clearing_house` when you
    need the canonical *workbook* label (which also applies entity mappings).
    """
    text = _APOSTROPHE_RE.sub("'", name)
    text = _DASH_RE.sub("-", text)
    return " ".join(text.split())


def safe_display_name(name: str) -> str:
    """Return a clean, human-readable display name for *name*.

    This is identical to :func:`canonicalize_name` but is exposed as a
    separate public symbol to make the intent explicit at call sites: the
    caller wants a label that is safe to show to the user, not necessarily
    a lookup key.
    """
    return canonicalize_name(name)


def _normalize_whitespace(name: str) -> str:
    """Trim leading/trailing whitespace and collapse internal runs of whitespace.

    .. deprecated::
        Prefer :func:`canonicalize_name` which also normalises punctuation.
    """
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
    normalized = canonicalize_name(name)
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
    normalized = canonicalize_name(name)
    return mappings.get(normalized, normalized)
