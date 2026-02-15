"""Backward-compatible exports for the raw NISA Trend parser."""

from __future__ import annotations

from pathlib import Path

from counter_risk.parsers.nisa import (
    NisaAllProgramsData,
    NisaChRow,
    NisaTotalsRow,
    parse_nisa_all_programs,
)

NisaTrendData = NisaAllProgramsData


def parse_nisa_trend(path: Path | str) -> NisaTrendData:
    """Parse raw NISA Trend workbooks into the Milestone 1 intermediate schema."""

    return parse_nisa_all_programs(path)


__all__ = [
    "NisaChRow",
    "NisaTotalsRow",
    "NisaTrendData",
    "parse_nisa_trend",
]
