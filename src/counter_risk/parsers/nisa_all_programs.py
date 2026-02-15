"""Backward-compatible exports for the raw NISA All Programs parser."""

from __future__ import annotations

from counter_risk.parsers.nisa import (
    NisaAllProgramsData,
    NisaChRow,
    NisaTotalsRow,
    parse_nisa_all_programs,
)

__all__ = [
    "NisaAllProgramsData",
    "NisaChRow",
    "NisaTotalsRow",
    "parse_nisa_all_programs",
]
