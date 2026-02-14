"""Compatibility writer wrapper for MOSERS workbook generation."""

from __future__ import annotations

from pathlib import Path
from counter_risk.mosers.workbook_generation import (
    generate_mosers_workbook as _generate_mosers_workbook_in_memory,
)


def generate_mosers_workbook(
    *,
    raw_nisa_path: str | Path,
    output_path: str | Path,
    as_of_date: object | None = None,
) -> Path:
    """Create a new MOSERS workbook file from raw NISA All Programs input."""

    destination = Path(output_path)
    if destination.suffix.lower() != ".xlsx":
        raise ValueError(f"output_path must point to an .xlsx file: {destination}")

    _ = as_of_date
    workbook = _generate_mosers_workbook_in_memory(raw_nisa_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(destination)
    workbook.close()
    return destination
