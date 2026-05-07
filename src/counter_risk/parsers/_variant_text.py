"""Shared helpers for parser variant detection from filename/sheet text."""

from __future__ import annotations

import re


def normalize_variant_text(value: str) -> str:
    """Lowercase ``value`` and collapse non-alphanumeric runs to single spaces.

    Both ``cprs_ch`` and ``cprs_fcm`` parsers run their variant heuristics
    against ``f"{file_path.name} {sheet_name}"`` after this normalization,
    so the helper lives here to keep variant matching consistent across
    parsers.
    """

    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
