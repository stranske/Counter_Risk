"""Parsing helpers for Counter Risk input rows."""

from __future__ import annotations

from collections.abc import Mapping

from counter_risk.normalize import normalize_clearing_house, normalize_counterparty


def parse_exposure_row(row: Mapping[str, str]) -> dict[str, str]:
    """Parse and normalize a raw exposure row from source workbooks."""

    return {
        "counterparty": normalize_counterparty(row["counterparty"]),
        "clearing_house": normalize_clearing_house(row["clearing_house"]),
        "program": row["program"],
    }
