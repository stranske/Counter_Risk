"""Naming conventions for PowerPoint deliverables produced by pipeline runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

_MASTER_BASE_NAME = "Monthly Counterparty Exposure Report (Master)"
_DISTRIBUTION_BASE_NAME = "Monthly Counterparty Exposure Report"


@dataclass(frozen=True)
class PptOutputNames:
    """Resolved output filenames for Master and Distribution PPT deliverables."""

    master_filename: str
    distribution_filename: str


def resolve_ppt_output_names(as_of_date: date) -> PptOutputNames:
    """Return deterministic PowerPoint output names for a pipeline run date."""

    date_token = as_of_date.isoformat()
    return PptOutputNames(
        master_filename=f"{_MASTER_BASE_NAME} - {date_token}.pptx",
        distribution_filename=f"{_DISTRIBUTION_BASE_NAME} - {date_token}.pptx",
    )
