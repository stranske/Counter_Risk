"""Limit breach computations for counterparty risk exposures."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from counter_risk.limits_config import LimitEntry, LimitsConfig

_NOTIONAL_KEYS = ("notional", "Notional", "exposure", "total", "amount")
_BREACH_COLUMNS = (
    "entity_type",
    "entity_name",
    "limit_kind",
    "actual_value",
    "limit_value",
    "breach_amount",
)
_ENTITY_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "counterparty": ("counterparty", "counterparty_name", "name"),
    "fcm": ("fcm", "fcm_name"),
    "clearing_house": ("clearing_house", "clearinghouse", "ch"),
    "segment": ("segment", "asset_class", "class"),
    "custom_group": ("custom_group", "custom_group_name", "group", "group_name"),
}


def _is_dataframe_like(value: Any) -> bool:
    return hasattr(value, "to_dict") and hasattr(value, "columns")


def _iter_rows(table: Any, *, arg_name: str) -> list[Mapping[str, Any]]:
    rows: list[Any]
    if _is_dataframe_like(table):
        rows = list(table.to_dict(orient="records"))
    elif isinstance(table, Iterable) and not isinstance(table, (str, bytes)):
        rows = list(table)
    else:
        raise TypeError(
            f"{arg_name} must be a pandas-like DataFrame or an iterable of row mappings"
        )

    validated: list[Mapping[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise TypeError(f"{arg_name} row at index {index} must be a mapping")
        validated.append(cast(Mapping[str, Any], row))
    return validated


def _to_dataframe_or_records(*, records: list[dict[str, Any]], columns: tuple[str, ...]) -> Any:
    try:
        import pandas as pd  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        return [{column: row.get(column) for column in columns} for row in records]

    frame = pd.DataFrame(records) if records else pd.DataFrame(columns=columns)
    for column in columns:
        if column not in frame.columns:
            frame[column] = 0.0
    return frame.loc[:, list(columns)]


def _records_from_table(table: Any, *, arg_name: str) -> list[dict[str, Any]]:
    rows = _iter_rows(table, arg_name=arg_name)
    return [dict(row) for row in rows]


def _normalize_entity_key(value: object) -> str:
    return "_".join(str(value).strip().split()).casefold()


def _find_notional(row: Mapping[str, Any]) -> float:
    for key in _NOTIONAL_KEYS:
        if key not in row:
            continue
        raw_value = row.get(key)
        if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
            raise ValueError("exposures_df contains blank notional values")
        try:
            return float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError("exposures_df notional values must be numeric") from exc
    raise ValueError(
        f"exposures_df rows must include one of the notional columns: {_NOTIONAL_KEYS}"
    )


def _find_entity_name(row: Mapping[str, Any], aliases: tuple[str, ...]) -> str | None:
    for key in aliases:
        if key not in row:
            continue
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _coerce_limits(limits_cfg: Any) -> LimitsConfig:
    if isinstance(limits_cfg, LimitsConfig):
        return limits_cfg

    if isinstance(limits_cfg, Mapping):
        try:
            return LimitsConfig.model_validate(limits_cfg)
        except ValidationError as exc:
            raise ValueError(f"limits_cfg is invalid: {exc}") from exc

    if isinstance(limits_cfg, Sequence) and not isinstance(limits_cfg, (str, bytes)):
        normalized_entries: list[LimitEntry | Mapping[str, Any]] = []
        for index, entry in enumerate(limits_cfg):
            if isinstance(entry, LimitEntry):
                normalized_entries.append(entry)
                continue
            if isinstance(entry, Mapping):
                normalized_entries.append(entry)
                continue
            raise TypeError(
                f"limits_cfg sequence items must be LimitEntry or mappings (index {index})"
            )
        try:
            return LimitsConfig.model_validate({"schema_version": 1, "limits": normalized_entries})
        except ValidationError as exc:
            raise ValueError(f"limits_cfg is invalid: {exc}") from exc

    raise TypeError("limits_cfg must be a LimitsConfig, mapping, or sequence of limit entries")


def check_limits(exposures_df: Any, limits_cfg: Any) -> Any:
    """Evaluate absolute-notional and percentage-of-total limit breaches.

    Returns a DataFrame-like table (or list of dict records if pandas is unavailable)
    with columns: entity_type, entity_name, limit_kind, actual_value, limit_value,
    and breach_amount.
    """

    rows = _iter_rows(exposures_df, arg_name="exposures_df")
    limits = _coerce_limits(limits_cfg)

    if not rows or not limits.limits:
        return _to_dataframe_or_records(records=[], columns=_BREACH_COLUMNS)

    total_abs_notional = sum(abs(_find_notional(row)) for row in rows)
    records: list[dict[str, Any]] = []

    for limit in limits.limits:
        aliases = _ENTITY_COLUMN_ALIASES[limit.entity_type]
        matched_abs_notional = 0.0
        found_match = False

        for row in rows:
            entity_name = _find_entity_name(row, aliases)
            if entity_name is None:
                continue
            if _normalize_entity_key(entity_name) != limit.entity_name:
                continue
            found_match = True
            matched_abs_notional += abs(_find_notional(row))

        if not found_match:
            continue

        if limit.limit_kind == "absolute_notional":
            actual_value = matched_abs_notional
        else:
            actual_value = (
                0.0 if total_abs_notional == 0.0 else matched_abs_notional / total_abs_notional
            )

        breach_amount = actual_value - limit.limit_value
        if breach_amount <= 0.0:
            continue

        records.append(
            {
                "entity_type": limit.entity_type,
                "entity_name": limit.entity_name,
                "limit_kind": limit.limit_kind,
                "actual_value": actual_value,
                "limit_value": float(limit.limit_value),
                "breach_amount": breach_amount,
            }
        )

    records.sort(
        key=lambda row: (
            str(row["entity_type"]).casefold(),
            str(row["entity_name"]).casefold(),
            str(row["limit_kind"]).casefold(),
        )
    )
    return _to_dataframe_or_records(records=records, columns=_BREACH_COLUMNS)


def write_limit_breaches_csv(breaches: Any, path: Path | str) -> None:
    """Write limit breach rows to CSV."""

    rows = _records_from_table(breaches, arg_name="breaches")
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        out_path.write_text("", encoding="utf-8")
        return

    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(_BREACH_COLUMNS), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
