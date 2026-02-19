"""Date derivation helpers for pipeline/reporting workflows."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any

from counter_risk.config import WorkflowConfig

_CPRS_HEADER_DATE_LABELS: tuple[str, ...] = (
    "cprs ch header date",
    "cprs-ch header date",
    "cprs_ch_header_date",
    "cprs ch as of date",
    "cprs_ch_as_of_date",
    "as of date",
    "as_of_date",
    "report date",
    "report_date",
)

_DATE_TOKEN_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}")


def derive_as_of_date(
    config: WorkflowConfig,
    cprs_headers: Mapping[str, Any] | Iterable[str] | None,
) -> date:
    """Derive as_of_date from config first, then CPRS headers."""

    if config.as_of_date is not None:
        return config.as_of_date

    inferred_date = _infer_date_from_cprs_headers(cprs_headers)
    if inferred_date is not None:
        return inferred_date

    raise ValueError("Unable to derive as_of_date from config.as_of_date or CPRS headers.")


def _infer_date_from_cprs_headers(
    cprs_headers: Mapping[str, Any] | Iterable[str] | None,
) -> date | None:
    if cprs_headers is None:
        return None

    if isinstance(cprs_headers, Mapping):
        for raw_key, raw_value in cprs_headers.items():
            key = _normalize_label(raw_key)
            if key not in _CPRS_HEADER_DATE_LABELS:
                continue
            parsed = _coerce_date(raw_value)
            if parsed is not None:
                return parsed
        return None

    for header in cprs_headers:
        if not isinstance(header, str):
            continue
        parsed = _extract_date_from_text(header)
        if parsed is not None:
            return parsed
    return None


def _extract_date_from_text(text: str) -> date | None:
    for token in _DATE_TOKEN_PATTERN.findall(text):
        parsed = _coerce_date(token)
        if parsed is not None:
            return parsed
    return None


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None

    stripped = value.strip()
    if not stripped:
        return None

    try:
        return date.fromisoformat(stripped)
    except ValueError:
        pass

    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(stripped, fmt).date()
        except ValueError:
            continue
    return None


def _normalize_label(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.lower().replace("-", " ").split())
