"""Shared name matching canonicalization helpers."""

from __future__ import annotations

import re

# Apostrophe variants -> ASCII apostrophe
_APOSTROPHE_RE = re.compile(r"[\u2018\u2019\u201b\u02bc`]")

# Hyphen/dash variants -> ASCII hyphen-minus
_DASH_RE = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]")


def canonicalize_match_key(value: str) -> str:
    """Return a deterministic case-insensitive key for name matching."""

    text = _APOSTROPHE_RE.sub("'", value)
    text = _DASH_RE.sub("-", text)
    return " ".join(text.split()).casefold()
