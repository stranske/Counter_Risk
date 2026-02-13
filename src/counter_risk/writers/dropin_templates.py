"""Drop-in template population helpers.

This module owns the Excel template write path used to generate operator-facing
Drop-In workbook outputs.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from counter_risk.normalize import normalize_clearing_house, normalize_counterparty

_COUNTERPARTY_COLUMNS = (
    "counterparty",
    "counterparty_name",
    "name",
    "clearing_house",
    "clearing_house_name",
)


def _normalize_label(name: str) -> str:
    """Return a deterministic normalized label for row matching."""

    cleaned = " ".join(str(name).split())
    return normalize_clearing_house(normalize_counterparty(cleaned)).casefold()


def _as_path(value: str | Path, *, field_name: str) -> Path:
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value.strip():
        return Path(value)
    msg = f"{field_name} must be a non-empty path-like string or Path"
    raise ValueError(msg)


def _coerce_breakdown(breakdown: Mapping[str, Any]) -> dict[str, float]:
    if not isinstance(breakdown, Mapping):
        raise TypeError("breakdown must be a mapping of metric names to numeric values")

    normalized: dict[str, float] = {}
    for key, raw_value in breakdown.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("breakdown keys must be non-empty strings")

        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"breakdown value for {key!r} must be numeric") from exc

        normalized[key] = value

    return normalized


def _is_dataframe_like(value: Any) -> bool:
    # Avoid hard dependency on pandas; this is sufficient for runtime validation.
    return hasattr(value, "columns") and hasattr(value, "to_dict")


def _iter_rows(exposures_df: Any) -> list[Mapping[str, Any]]:
    if _is_dataframe_like(exposures_df):
        rows = exposures_df.to_dict(orient="records")
    elif isinstance(exposures_df, Iterable) and not isinstance(exposures_df, (str, bytes)):
        rows = list(exposures_df)
    else:
        raise TypeError(
            "exposures_df must be a pandas-like DataFrame or an iterable of row mappings"
        )

    if not rows:
        return []

    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise TypeError(f"exposures_df row at index {index} must be a mapping")

    return rows


def _build_exposure_index(rows: list[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    """Index rows by normalized counterparty/clearing-house label."""

    indexed: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        label = None
        for key in _COUNTERPARTY_COLUMNS:
            raw_name = row.get(key)
            if isinstance(raw_name, str) and raw_name.strip():
                label = _normalize_label(raw_name)
                break

        if label is None:
            continue

        indexed[label] = row

    return indexed


def fill_dropin_template(
    template_path: str | Path,
    exposures_df: Any,
    breakdown: Mapping[str, Any],
    *,
    output_path: str | Path,
) -> Path:
    """Load a drop-in template and write a populated output workbook.

    The population logic is intentionally conservative in this first slice: inputs
    are validated, row labels are indexed for deterministic matching, and the
    template is loaded/saved to guarantee a valid output workbook for follow-on
    cell population tasks.
    """

    template_file = _as_path(template_path, field_name="template_path")
    output_file = _as_path(output_path, field_name="output_path")

    if not template_file.exists():
        raise FileNotFoundError(f"Template workbook not found: {template_file}")

    if template_file.suffix.lower() != ".xlsx":
        raise ValueError(f"template_path must point to an .xlsx file: {template_file}")

    rows = _iter_rows(exposures_df)
    _ = _build_exposure_index(rows)
    _ = _coerce_breakdown(breakdown)

    try:
        from openpyxl import load_workbook
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "openpyxl is required to fill drop-in templates. "
            "Install project dev dependencies to enable this feature."
        ) from exc

    try:
        workbook = load_workbook(filename=template_file)
    except OSError as exc:
        raise ValueError(f"Unable to load template workbook: {template_file}") from exc

    output_file.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_file)
    workbook.close()
    return output_file
