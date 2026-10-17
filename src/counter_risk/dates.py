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


# Independent evidence deliberately uses a narrower grammar than legacy fallback.
_REPORT_DATE_LABEL = re.compile(
    r"^\s*(?:as[ _-]+of(?:[ _-]+date)?|report[ _-]+date|cprs[ _-]+ch[ _-]+header[ _-]+date)\s*:?\s*",
    re.IGNORECASE,
)

_REPORT_DATE_TOKEN_PATTERN = re.compile(rf"(?:{_DATE_TOKEN_PATTERN.pattern})(?![\w/-])")
# Evidence counts incomplete numeric dates too; only the leading complete token
# can identify a period. Keep this separate from the legacy fallback grammar.
_REPORT_DATE_CANDIDATE_PATTERN = re.compile(r"\d{4}-\d*(?:-\d*)?|\d{1,2}/\d*(?:/\d*)?")
_GENERATED_REPORT_DATE_MARKER = re.compile(
    r"^\s*(?:Generated from config as_of_date\b|Counter-risk generated\b|CPRS CH Header Date\b)",
    re.IGNORECASE,
)


def source_report_date_evidence(
    *, variant: str, path: str | None, headers: Iterable[str], generated: bool = False
) -> dict[str, Any]:
    """Classify bounded source headers; unverified evidence never confirms a match."""
    lines = list(headers)
    generated = generated or any(_GENERATED_REPORT_DATE_MARKER.match(line) for line in lines)
    observations: list[dict[str, str]] = []
    invalid = False
    for line in lines:
        label = _REPORT_DATE_LABEL.search(line)
        if label is None:
            continue
        value_text = line[label.end() :]
        # Count all date-like tokens before validating the leading date. Otherwise a
        # malformed second date can be filtered out and falsely confirm the first.
        tokens = _REPORT_DATE_CANDIDATE_PATTERN.findall(value_text)
        leading_date = _REPORT_DATE_TOKEN_PATTERN.match(value_text)
        parsed = _coerce_date(leading_date.group()) if leading_date else None
        if len(tokens) != 1 or parsed is None:
            invalid = True
            continue
        observations.append({"date": str(parsed), "header_text": line})
    dates = sorted({entry["date"] for entry in observations})
    status = (
        "generated"
        if generated
        else (
            "ambiguous"
            if invalid or len(dates) > 1
            else "identified" if len(dates) == 1 else "unverified"
        )
    )
    return {
        "variant": variant,
        "path": path,
        "status": status,
        "report_date": dates[0] if status == "identified" else None,
        "observations": observations,
    }


def compare_source_report_dates(
    *, configured_date: date | None, evidence: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    """Compare every reliable source, independently of authoritative date resolution."""
    sources = list(evidence)
    identified = [entry for entry in sources if entry["status"] == "identified"]
    dates = {entry["report_date"] for entry in identified}
    inter_variant_conflict = len(dates) > 1
    config_conflicts = [
        entry["variant"]
        for entry in identified
        if configured_date is not None and entry["report_date"] != configured_date.isoformat()
    ]
    return {
        "configured_date": configured_date.isoformat() if configured_date else None,
        "sources": sources,
        "has_conflict": bool(config_conflicts) or inter_variant_conflict,
        "config_conflict_variants": config_conflicts,
        "inter_variant_conflict": inter_variant_conflict,
        "status": (
            "conflict"
            if config_conflicts or inter_variant_conflict
            else "consistent" if len(identified) == len(sources) and identified else "unverified"
        ),
    }
