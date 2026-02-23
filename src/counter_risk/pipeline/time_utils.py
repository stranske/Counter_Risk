"""Time helpers used by pipeline code."""

from __future__ import annotations

import datetime as _dt

UTC = getattr(_dt, "UTC", _dt.timezone.utc)


def utc_now_isoformat() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return _dt.datetime.now(tz=UTC).isoformat()
