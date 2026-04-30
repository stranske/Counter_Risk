"""Date derivation helpers for pipeline/reporting workflows."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, tzinfo
from types import MappingProxyType
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

AS_OF_SOURCE_CONFIG = "config"
AS_OF_SOURCE_HEADER_MAPPING = "cprs_header_mapping"
AS_OF_SOURCE_HEADER_TEXT = "cprs_header_text"
RUN_DATE_SOURCE_CONFIG = "config"
RUN_DATE_SOURCE_SYSTEM_CLOCK = "system_clock"


@dataclass(frozen=True)
class DateResolution:
    """Resolved date plus metadata describing how it was derived."""

    value: date
    source: str
    details: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def to_manifest_entry(self) -> dict[str, Any]:
        """Render as a JSON-serializable manifest entry."""

        return {
            "value": self.value.isoformat(),
            "source": self.source,
            "details": dict(self.details),
        }


def resolve_as_of_date(
    config: WorkflowConfig,
    cprs_headers: Mapping[str, Any] | Iterable[str] | None,
) -> DateResolution:
    """Resolve as_of_date with the source of the resolved value."""

    if config.as_of_date is not None:
        return DateResolution(
            value=config.as_of_date,
            source=AS_OF_SOURCE_CONFIG,
            details=MappingProxyType({"config_field": "as_of_date"}),
        )

    inferred = _infer_as_of_from_cprs_headers(cprs_headers)
    if inferred is not None:
        return inferred

    raise ValueError("Unable to derive as_of_date from config.as_of_date or CPRS headers.")


def resolve_run_date(config: WorkflowConfig, tzinfo: tzinfo | None = None) -> DateResolution:
    """Resolve run_date with the source of the resolved value."""

    if config.run_date is not None:
        return DateResolution(
            value=config.run_date,
            source=RUN_DATE_SOURCE_CONFIG,
            details=MappingProxyType({"config_field": "run_date"}),
        )

    if tzinfo is not None:
        clock_value = datetime.now(tz=tzinfo).date()
        tz_label = str(tzinfo)
    else:
        clock_value = datetime.now().astimezone().date()
        tz_label = "local"

    return DateResolution(
        value=clock_value,
        source=RUN_DATE_SOURCE_SYSTEM_CLOCK,
        details=MappingProxyType({"tzinfo": tz_label}),
    )


def derive_as_of_date(
    config: WorkflowConfig,
    cprs_headers: Mapping[str, Any] | Iterable[str] | None,
) -> date:
    """Derive as_of_date from config first, then CPRS headers."""

    return resolve_as_of_date(config, cprs_headers).value


def derive_run_date(config: WorkflowConfig, tzinfo: tzinfo | None = None) -> date:
    """Derive run_date from config or default to today's local date."""

    return resolve_run_date(config, tzinfo=tzinfo).value


def _infer_as_of_from_cprs_headers(
    cprs_headers: Mapping[str, Any] | Iterable[str] | None,
) -> DateResolution | None:
    if cprs_headers is None:
        return None

    if isinstance(cprs_headers, Mapping):
        for raw_key, raw_value in cprs_headers.items():
            key = _normalize_label(raw_key)
            if key not in _CPRS_HEADER_DATE_LABELS:
                continue
            parsed = _coerce_date(raw_value)
            if parsed is not None:
                return DateResolution(
                    value=parsed,
                    source=AS_OF_SOURCE_HEADER_MAPPING,
                    details=MappingProxyType(
                        {
                            "header_label": str(raw_key),
                            "raw_value": str(raw_value),
                        }
                    ),
                )
        return None

    for header in cprs_headers:
        if not isinstance(header, str):
            continue
        token, parsed = _extract_date_from_text(header)
        if parsed is not None:
            return DateResolution(
                value=parsed,
                source=AS_OF_SOURCE_HEADER_TEXT,
                details=MappingProxyType({"header_text": header, "matched_token": token or ""}),
            )
    return None


def _extract_date_from_text(text: str) -> tuple[str | None, date | None]:
    for token in _DATE_TOKEN_PATTERN.findall(text):
        parsed = _coerce_date(token)
        if parsed is not None:
            return token, parsed
    return None, None


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
