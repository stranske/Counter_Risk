"""Typed provenance records for manifest facts."""

from __future__ import annotations

from typing import TypedDict


class Evidence(TypedDict):
    """Source pointer for a manifest fact."""

    source_id: str
    sheet: str | None
    row: int | None
    method: str
    confidence: float | None


def top_exposure_evidence(
    *, variant: str, sheet: object, row: object, method: str = "nisa_parser"
) -> Evidence:
    """Build evidence for a top exposure row using the manifest input key namespace."""

    source_id = "mosers_all_programs_xlsx" if variant == "all_programs" else f"mosers_{variant}_xlsx"
    source_sheet = str(sheet).strip() if sheet is not None and str(sheet).strip() else None
    source_row = int(row) if isinstance(row, int) and row > 0 else None
    return {
        "source_id": source_id,
        "sheet": source_sheet,
        "row": source_row,
        "method": method,
        "confidence": None,
    }
