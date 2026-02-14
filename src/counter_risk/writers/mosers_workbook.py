"""Generate MOSERS-format workbooks from raw NISA monthly input."""

from __future__ import annotations

from pathlib import Path
from shutil import copyfile

from counter_risk.mosers.template import get_mosers_template_path
from counter_risk.parsers.nisa_all_programs import parse_nisa_all_programs


def generate_mosers_workbook(
    *,
    raw_nisa_path: str | Path,
    output_path: str | Path,
    as_of_date: object | None = None,
) -> Path:
    """Create a new MOSERS workbook from raw NISA All Programs input."""

    destination = Path(output_path)
    if destination.suffix.lower() != ".xlsx":
        raise ValueError(f"output_path must point to an .xlsx file: {destination}")

    # Keep parser validation in the generation path so malformed inputs fail early.
    _ = as_of_date
    parse_nisa_all_programs(raw_nisa_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    copyfile(get_mosers_template_path(), destination)
    return destination
