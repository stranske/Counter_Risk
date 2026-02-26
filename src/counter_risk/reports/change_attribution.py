"""Change attribution helpers with explicit confidence labeling."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

_COUNTERPARTY_COLUMNS: tuple[str, ...] = ("counterparty", "name")
_NOTIONAL_COLUMNS: tuple[str, ...] = ("Notional", "notional")
_DELTA_COLUMNS: tuple[str, ...] = (
    "NotionalChange",
    "NotionalChangeFromPriorMonth",
    "notional_change",
)
_FUZZY_MATCH_THRESHOLD = 0.82
_MEDIUM_RAW_LENGTH_DRIFT = 3
_DELTA_TOLERANCE = 1e-6

_REASON_EXACT_KEY_MATCH = "exact_key_match"
_REASON_NORMALIZED_MEDIUM = "normalized_name_match_minor_differences"
_REASON_NORMALIZED_LOW = "normalized_name_match_requires_review"
_REASON_FUZZY_LOW = "fuzzy_name_match_partial_similarity"
_REASON_UNMATCHED_NEW = "new_or_unmatched_current_row"
_REASON_UNMATCHED_MISSING_PRIOR = "missing_prior_data"
_LOW_CONFIDENCE_REASONS: frozenset[str] = frozenset(
    {
        _REASON_NORMALIZED_LOW,
        _REASON_FUZZY_LOW,
        _REASON_UNMATCHED_NEW,
        _REASON_UNMATCHED_MISSING_PRIOR,
    }
)


@dataclass(frozen=True)
class _ExposureRow:
    counterparty: str
    normalized_counterparty: str
    notional: float
    supplied_delta: float | None


def _records(table: Any, *, arg_name: str) -> list[dict[str, Any]]:
    if isinstance(table, Mapping):
        raise TypeError(
            f"{arg_name} must be a pandas-like DataFrame or iterable of row mappings, "
            f"not {type(table)!r}"
        )
    if hasattr(table, "to_dict"):
        records = table.to_dict(orient="records")
    elif isinstance(table, Iterable):
        records = list(table)
    else:
        raise TypeError(
            f"{arg_name} must be a pandas-like DataFrame or iterable of row mappings, "
            f"not {type(table)!r}"
        )

    if not all(isinstance(row, Mapping) for row in records):
        raise TypeError(f"{arg_name} must contain only row mappings")
    return [dict(row) for row in records]


def _first_string(record: Mapping[str, Any], candidates: tuple[str, ...]) -> str:
    for key in candidates:
        value = record.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _first_float(record: Mapping[str, Any], candidates: tuple[str, ...]) -> float:
    for key in candidates:
        value = record.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _optional_float(record: Mapping[str, Any], candidates: tuple[str, ...]) -> float | None:
    for key in candidates:
        if key not in record:
            continue
        value = record.get(key)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


def _normalize_name(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalnum())


def _parse_exposure_rows(table: Any, *, arg_name: str) -> list[_ExposureRow]:
    rows: list[_ExposureRow] = []
    for record in _records(table, arg_name=arg_name):
        counterparty = _first_string(record, _COUNTERPARTY_COLUMNS)
        if not counterparty:
            continue
        rows.append(
            _ExposureRow(
                counterparty=counterparty,
                normalized_counterparty=_normalize_name(counterparty),
                notional=_first_float(record, _NOTIONAL_COLUMNS),
                supplied_delta=_optional_float(record, _DELTA_COLUMNS),
            )
        )
    return rows


def _best_fuzzy_match(
    *,
    current_normalized: str,
    prior_by_normalized: Mapping[str, _ExposureRow],
    used_keys: set[str],
) -> _ExposureRow | None:
    best: tuple[float, _ExposureRow] | None = None
    for normalized_name, row in prior_by_normalized.items():
        if normalized_name in used_keys:
            continue
        ratio = SequenceMatcher(None, current_normalized, normalized_name).ratio()
        if ratio < _FUZZY_MATCH_THRESHOLD:
            continue
        if best is None or ratio > best[0]:
            best = (ratio, row)
    return best[1] if best is not None else None


def _is_minor_normalized_difference(*, current_name: str, prior_name: str) -> bool:
    current = current_name.strip()
    prior = prior_name.strip()
    if not current or not prior:
        return False
    if current == prior:
        return False
    current_normalized = _normalize_name(current)
    prior_normalized = _normalize_name(prior)
    if current_normalized != prior_normalized:
        return False
    raw_length_drift = abs(len(current) - len(prior))
    return raw_length_drift <= _MEDIUM_RAW_LENGTH_DRIFT


def _unmatched_reason(*, has_any_prior_rows: bool) -> str:
    if has_any_prior_rows:
        return _REASON_UNMATCHED_NEW
    return _REASON_UNMATCHED_MISSING_PRIOR


def attribute_changes(current_df: Any, prior_df: Any) -> dict[str, Any]:
    """Attribute period-over-period notional moves with explicit confidence labels."""

    current_rows = _parse_exposure_rows(current_df, arg_name="current_df")
    prior_rows = _parse_exposure_rows(prior_df, arg_name="prior_df")

    prior_by_exact = {row.counterparty: row for row in prior_rows}
    prior_by_normalized = {row.normalized_counterparty: row for row in prior_rows}
    used_prior_normalized: set[str] = set()
    has_any_prior_rows = bool(prior_rows)

    report_rows: list[dict[str, Any]] = []
    unmatched_count = 0
    low_confidence_count = 0

    for current in sorted(current_rows, key=lambda row: row.counterparty.casefold()):
        prior_match: _ExposureRow | None = None
        reason = _unmatched_reason(has_any_prior_rows=has_any_prior_rows)
        match_type = "unmatched"
        confidence = "Low"

        if current.counterparty in prior_by_exact:
            prior_match = prior_by_exact[current.counterparty]
            match_type = "exact"
            reason = _REASON_EXACT_KEY_MATCH
            delta = current.notional - prior_match.notional
            supplied_delta = current.supplied_delta
            has_clean_delta = (
                supplied_delta is None or abs(delta - supplied_delta) <= _DELTA_TOLERANCE
            )
            confidence = "High" if has_clean_delta else "Medium"
        elif current.normalized_counterparty in prior_by_normalized:
            prior_match = prior_by_normalized[current.normalized_counterparty]
            match_type = "normalized"
            if _is_minor_normalized_difference(
                current_name=current.counterparty,
                prior_name=prior_match.counterparty,
            ):
                reason = _REASON_NORMALIZED_MEDIUM
                confidence = "Medium"
            else:
                reason = _REASON_NORMALIZED_LOW
                confidence = "Low"
        else:
            prior_match = _best_fuzzy_match(
                current_normalized=current.normalized_counterparty,
                prior_by_normalized=prior_by_normalized,
                used_keys=used_prior_normalized,
            )
            if prior_match is not None:
                match_type = "fuzzy"
                reason = _REASON_FUZZY_LOW
                confidence = "Low"

        if prior_match is None:
            prior_notional = 0.0
            unmatched_count += 1
        else:
            prior_notional = prior_match.notional
            used_prior_normalized.add(prior_match.normalized_counterparty)

        notional_change = current.notional - prior_notional
        is_low_confidence = reason in _LOW_CONFIDENCE_REASONS
        if is_low_confidence:
            low_confidence_count += 1

        report_rows.append(
            {
                "counterparty": current.counterparty,
                "matched_prior_counterparty": (
                    prior_match.counterparty if prior_match is not None else ""
                ),
                "current_notional": current.notional,
                "prior_notional": prior_notional,
                "notional_change": notional_change,
                "match_type": match_type,
                "confidence": confidence,
                "attribution_reason": reason,
                "is_unmatched": prior_match is None,
                "is_low_confidence": is_low_confidence,
            }
        )

    unattributed_remainder = sum(
        row["notional_change"]
        for row in report_rows
        if row["is_unmatched"] or row["is_low_confidence"]
    )

    return {
        "rows": report_rows,
        "summary": {
            "total_current_rows": len(current_rows),
            "total_prior_rows": len(prior_rows),
            "unmatched_rows": unmatched_count,
            "low_confidence_rows": low_confidence_count,
            "unattributed_remainder": unattributed_remainder,
        },
    }


def render_change_attribution_markdown(report: Mapping[str, Any]) -> str:
    """Render a compact markdown report from ``attribute_changes`` output."""

    summary = report.get("summary", {})
    rows = report.get("rows", [])
    lines = [
        "# Change Attribution",
        "",
        f"- Total current rows: {summary.get('total_current_rows', 0)}",
        f"- Total prior rows: {summary.get('total_prior_rows', 0)}",
        f"- Unmatched rows: {summary.get('unmatched_rows', 0)}",
        f"- Low-confidence rows: {summary.get('low_confidence_rows', 0)}",
        f"- Unattributed remainder: {summary.get('unattributed_remainder', 0.0):.6f}",
        "",
        "| Counterparty | Prior Match | Current | Prior | Change | Match | Confidence | Reason |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('counterparty', '')} | "
            f"{row.get('matched_prior_counterparty', '')} | "
            f"{float(row.get('current_notional', 0.0)):.6f} | "
            f"{float(row.get('prior_notional', 0.0)):.6f} | "
            f"{float(row.get('notional_change', 0.0)):.6f} | "
            f"{row.get('match_type', '')} | "
            f"{row.get('confidence', '')} | "
            f"{row.get('attribution_reason', '')} |"
        )
    return "\n".join(lines) + "\n"


def write_change_attribution_csv(*, report: Mapping[str, Any], path: Path) -> None:
    """Write deterministic CSV rows for change attribution."""

    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=(
                "counterparty",
                "matched_prior_counterparty",
                "current_notional",
                "prior_notional",
                "notional_change",
                "match_type",
                "confidence",
                "attribution_reason",
                "is_unmatched",
                "is_low_confidence",
            ),
        )
        writer.writeheader()
        writer.writerows(report.get("rows", []))


def write_change_attribution_markdown(*, report: Mapping[str, Any], path: Path) -> None:
    """Write markdown summary for change attribution."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_change_attribution_markdown(report), encoding="utf-8")
