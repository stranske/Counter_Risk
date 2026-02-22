"""Tests for pipeline time utility helpers."""

from __future__ import annotations

import datetime as dt

from counter_risk.pipeline import time_utils


def test_utc_constant_uses_datetime_utc() -> None:
    assert time_utils.UTC is dt.UTC


def test_utc_now_isoformat_returns_utc_timestamp() -> None:
    timestamp = time_utils.utc_now_isoformat()

    parsed = dt.datetime.fromisoformat(timestamp)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == dt.timedelta(0)
