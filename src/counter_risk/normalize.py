"""Deterministic name normalization helpers for Counter Risk entities.

This module centralizes spreadsheet/header name cleanup so parser and writer
steps resolve to stable canonical labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from counter_risk.name_registry import NameRegistryConfig, load_name_registry


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


def _normalize_whitespace(name: str) -> str:
    """Trim leading/trailing whitespace and collapse internal runs of whitespace."""

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
        for alias in entry.aliases:
            lookup[_normalize_whitespace(alias).casefold()] = entry.display_name
    return lookup


def resolve_counterparty(
    name: str,
    *,
    registry_path: str | Path = Path("config/name_registry.yml"),
) -> NameResolution:
    """Resolve counterparty name with registry-first semantics."""

    normalized = _normalize_whitespace(name)
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


def normalize_clearing_house(name: str) -> str:
    """Normalize a clearing house name to the canonical historical workbook label."""

    normalized = _normalize_whitespace(name)
    return _CLEARING_HOUSE_FALLBACK_MAPPINGS.get(normalized, normalized)
