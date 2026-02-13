"""Writer helpers for normalized Counter Risk output records."""

from __future__ import annotations

from counter_risk.normalize import normalize_clearing_house, normalize_counterparty


def build_exposure_record(
    counterparty: str,
    clearing_house: str,
    exposure: float,
) -> dict[str, float | str]:
    """Build a normalized record for workbook/PPT output generation."""

    return {
        "counterparty": normalize_counterparty(counterparty),
        "clearing_house": normalize_clearing_house(clearing_house),
        "exposure": exposure,
    }
