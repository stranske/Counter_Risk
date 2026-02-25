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
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from counter_risk.name_registry import NameRegistryConfig, load_name_registry

# Apostrophe variants → ASCII apostrophe
_APOSTROPHE_RE = re.compile(r"[\u2018\u2019\u201b\u02bc`]")

# Hyphen/dash variants → ASCII hyphen-minus
_DASH_RE = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]")


@dataclass(frozen=True)
class NameResolution:
    """A resolved counterparty name and mapping origin."""

    raw_name: str
    canonical_name: str
    source: Literal["registry", "fallback", "unmapped"]


_COUNTERPARTY_FALLBACK_MAPPINGS = {
    "Citigroup": "Citibank",
    "Bank of America, NA": "Bank of America",
    "Bank of America NA": "Bank of America",
    "Goldman Sachs Int'l": "Goldman Sachs",
    "Societe Generale": "Soc Gen",
    "Barclays Bank PLC": "Barclays",
}

_CLEARING_HOUSE_FALLBACK_MAPPINGS = {
    "CME Clearing House": "CME",
    "ICE Clear U.S.": "ICE",
    "ICE Clear US": "ICE",
    "ICE Clear Europe": "ICE Euro",
    "EUREX Clearing": "EUREX",
    "Japan Securities Clearing Corporation": "Japan SCC",
    "Korea Exchange (in-house)": "Korea Exchange",
}


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

    Unlike the matching key returned by :func:`canonicalize_name`, this
    function **only** collapses whitespace.  Unicode punctuation variants
    (curly apostrophes, en-dashes, em-dashes, etc.) are intentionally left
    intact so the rendered text looks natural to human readers.

    Use :func:`canonicalize_name` (the *matching key*) when you need a
    stable token for dictionary lookups or string comparisons.  Use this
    function when you need a label safe to display in a report or UI.
    """
    return " ".join(name.split())


def _normalize_whitespace(name: str) -> str:
    """Trim leading/trailing whitespace and collapse internal runs of whitespace.

    .. deprecated::
        Prefer :func:`canonicalize_name` which also normalises punctuation.
    """
    return " ".join(name.split())


@lru_cache(maxsize=8)
def _load_alias_lookup(registry_path: str) -> dict[str, str]:
    try:
        registry = load_name_registry(Path(registry_path))
    except ValueError:
        return {}
    return _build_alias_lookup(registry)


def _build_alias_lookup(registry: NameRegistryConfig) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for entry in registry.entries:
        lookup[canonicalize_name(entry.canonical_key).casefold()] = entry.display_name
        lookup[canonicalize_name(entry.display_name).casefold()] = entry.display_name
        for alias in entry.aliases:
            lookup[canonicalize_name(alias).casefold()] = entry.display_name
    return lookup


def resolve_counterparty(
    name: str,
    *,
    registry_path: str | Path = Path("config/name_registry.yml"),
) -> NameResolution:
    """Resolve counterparty name with registry-first semantics."""

    normalized = canonicalize_name(name)
    alias_lookup = _load_alias_lookup(str(Path(registry_path).resolve()))
    registry_match = alias_lookup.get(normalized.casefold())
    if registry_match is not None:
        return NameResolution(raw_name=name, canonical_name=registry_match, source="registry")

    fallback_match = _COUNTERPARTY_FALLBACK_MAPPINGS.get(normalized)
    if fallback_match is not None:
        return NameResolution(raw_name=name, canonical_name=fallback_match, source="fallback")

    return NameResolution(raw_name=name, canonical_name=normalized, source="unmapped")


def normalize_counterparty(name: str) -> str:
    """Normalize a counterparty name to the canonical historical workbook label."""

    return resolve_counterparty(name).canonical_name


def resolve_clearing_house(
    name: str,
    *,
    registry_path: str | Path = Path("config/name_registry.yml"),
) -> NameResolution:
    """Resolve clearing house name with registry-first semantics."""

    normalized = canonicalize_name(name)
    alias_lookup = _load_alias_lookup(str(Path(registry_path).resolve()))
    registry_match = alias_lookup.get(normalized.casefold())
    if registry_match is not None:
        return NameResolution(raw_name=name, canonical_name=registry_match, source="registry")

    fallback_match = _CLEARING_HOUSE_FALLBACK_MAPPINGS.get(normalized)
    if fallback_match is not None:
        return NameResolution(raw_name=name, canonical_name=fallback_match, source="fallback")

    return NameResolution(raw_name=name, canonical_name=normalized, source="unmapped")


def normalize_clearing_house(name: str) -> str:
    """Normalize a clearing house name to the canonical historical workbook label."""

    normalized = _normalize_whitespace(name)
    return _CLEARING_HOUSE_FALLBACK_MAPPINGS.get(normalized, normalized)
