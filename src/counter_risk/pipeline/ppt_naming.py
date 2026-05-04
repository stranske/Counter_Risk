"""Naming conventions for PowerPoint deliverables produced by pipeline runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

_MASTER_BASE_NAME = "Monthly Counterparty Exposure Report (Master)"
_DISTRIBUTION_BASE_NAME = "Monthly Counterparty Exposure Report"


@dataclass(frozen=True)
class PptOutputNames:
    """Resolved output filenames for Master and Distribution PPT deliverables."""

    master_filename: str
    distribution_filename: str


def master_ppt_filename(as_of_date: date) -> str:
    """Return the canonical Master PPT filename for an as-of date."""

    resolved_as_of_date = _coerce_as_of_date(as_of_date)
    return f"{_MASTER_BASE_NAME} - {resolved_as_of_date.isoformat()}.pptx"


def distribution_ppt_filename(as_of_date: date) -> str:
    """Return the canonical Distribution PPT filename for an as-of date."""

    resolved_as_of_date = _coerce_as_of_date(as_of_date)
    return f"{_DISTRIBUTION_BASE_NAME} - {resolved_as_of_date.isoformat()}.pptx"


def resolve_ppt_output_names(as_of_date: date) -> PptOutputNames:
    """Return deterministic PowerPoint output names for a pipeline run date."""

    resolved_as_of_date = _coerce_as_of_date(as_of_date)
    return PptOutputNames(
        master_filename=master_ppt_filename(resolved_as_of_date),
        distribution_filename=distribution_ppt_filename(resolved_as_of_date),
    )


def _coerce_as_of_date(as_of_date: date) -> date:
    """Normalize date-like values to a date token used in output names."""

    if isinstance(as_of_date, datetime):
        return as_of_date.date()
    return as_of_date
