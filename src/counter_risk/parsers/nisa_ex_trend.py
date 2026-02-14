"""Backward-compatible exports for the raw NISA Ex Trend parser."""

from __future__ import annotations

from pathlib import Path

from counter_risk.parsers.nisa import (
    NisaAllProgramsData,
    NisaChRow,
    NisaTotalsRow,
    parse_nisa_all_programs,
)

NisaExTrendData = NisaAllProgramsData


def parse_nisa_ex_trend(path: Path | str) -> NisaExTrendData:
    """Parse raw NISA Ex Trend workbooks into the Milestone 1 intermediate schema."""

    return parse_nisa_all_programs(path)


__all__ = [
    "NisaChRow",
    "NisaExTrendData",
    "NisaTotalsRow",
    "parse_nisa_ex_trend",
]
