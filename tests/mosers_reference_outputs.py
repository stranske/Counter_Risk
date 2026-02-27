"""Approved MOSERS reference output fixtures used for range-level comparisons."""

from __future__ import annotations

from pathlib import Path

_REFERENCE_OUTPUTS = {
    "all_programs": Path(
        "tests/fixtures/MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx"
    ),
    "ex_trend": Path("tests/fixtures/MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx"),
    "trend": Path("tests/fixtures/MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx"),
}


def get_mosers_reference_output_paths() -> dict[str, Path]:
    """Return approved per-variant MOSERS reference workbook paths."""

    return dict(_REFERENCE_OUTPUTS)
