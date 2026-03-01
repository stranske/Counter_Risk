"""Formatting profile helpers for operator-facing numeric output controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

DEFAULT_FORMATTING_PROFILE: Final[str] = "default"


@dataclass(frozen=True)
class FormattingPolicy:
    """Resolved numeric formatting behavior for one runtime profile."""

    profile: str
    notional_number_format: str | None
    counterparties_number_format: str | None


_FORMATTING_POLICIES: Final[dict[str, FormattingPolicy]] = {
    "default": FormattingPolicy(
        profile="default",
        notional_number_format=None,
        counterparties_number_format=None,
    ),
    "currency": FormattingPolicy(
        profile="currency",
        notional_number_format="$#,##0.00;[Red]-$#,##0.00",
        counterparties_number_format="0",
    ),
    "accounting": FormattingPolicy(
        profile="accounting",
        notional_number_format='_($* #,##0.00_);_($* (#,##0.00);_($* "-"??_);_(@_)',
        counterparties_number_format="0",
    ),
    "plain": FormattingPolicy(
        profile="plain",
        notional_number_format="#,##0.00",
        counterparties_number_format="0",
    ),
}


def normalize_formatting_profile(profile: str | None) -> str:
    """Return a normalized profile key with safe fallback to ``default``."""

    if profile is None:
        return DEFAULT_FORMATTING_PROFILE
    normalized = profile.strip().lower()
    if not normalized:
        return DEFAULT_FORMATTING_PROFILE
    return normalized if normalized in _FORMATTING_POLICIES else DEFAULT_FORMATTING_PROFILE


def resolve_formatting_policy(profile: str | None) -> FormattingPolicy:
    """Resolve one formatting policy from a runtime profile selector."""

    normalized = normalize_formatting_profile(profile)
    return _FORMATTING_POLICIES[normalized]

