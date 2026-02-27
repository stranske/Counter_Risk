"""Backward-compatible exports for the raw NISA All Programs parser."""

from __future__ import annotations

from counter_risk.parsers.nisa import (
    NisaAllProgramsData,
    NisaAllProgramsInputStructure,
    NisaChRow,
    NisaTotalsRow,
    get_nisa_all_programs_input_structure,
    parse_nisa_all_programs,
)

__all__ = [
    "NisaAllProgramsData",
    "NisaAllProgramsInputStructure",
    "NisaChRow",
    "NisaTotalsRow",
    "get_nisa_all_programs_input_structure",
    "parse_nisa_all_programs",
]
