"""Rollup computations for historical class sheets and run summaries."""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, cast

_COUNTERPARTY_KEYS = ("counterparty", "counterparty_name", "name")
_ASSET_CLASS_KEYS = ("asset_class", "class", "segment")
_NOTIONAL_KEYS = ("notional", "exposure", "total", "amount")
_PRIOR_NOTIONAL_KEYS = (
    "prior_notional",
    "prior_month_notional",
    "notional_prior_month",
    "notional_prior",
    "prior",
)

_TOTAL_COLUMNS = (
    "group_type",
    "group_name",
    "notional",
    "prior_notional",
    "notional_change",
)

_TOP_EXPOSURE_COLUMNS = ("counterparty", "asset_class", "notional")
_TOP_CHANGE_COLUMNS = (
    "group_type",
    "group_name",
    "notional",
    "prior_notional",
    "notional_change",
    "absolute_change",
)

_CONCENTRATION_GROUP_COLUMNS = ("variant", "segment")
_CONCENTRATION_METRIC_COLUMNS = ("top5_share", "top10_share", "hhi")


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


def _find_string(row: Mapping[str, Any], keys: tuple[str, ...], *, field: str) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError(f"Row missing required {field} column value from aliases {keys}")


def _find_numeric(
    row: Mapping[str, Any],
    keys: tuple[str, ...],
    *,
    field: str,
    default: float | None = None,
) -> float:
    for key in keys:
        if key not in row:
            continue

        raw_value = row.get(key)
        if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
            break

        try:
            return float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Row value for {field!r} must be numeric") from exc

    if default is not None:
        return default

    raise ValueError(f"Row missing required numeric {field} column from aliases {keys}")


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


def compute_totals(exposures_df: Any) -> Any:
    """Aggregate exposures by counterparty and asset class.

    Output schema columns:
    - group_type: one of "counterparty" or "asset_class"
    - group_name: counterparty or asset class label
    - notional: current notional total
    - prior_notional: prior notional total if available (0.0 otherwise)
    - notional_change: `notional - prior_notional`
    """

    rows = _iter_rows(exposures_df, arg_name="exposures_df")
    if not rows:
        return _to_dataframe_or_records(records=[], columns=_TOTAL_COLUMNS)

    by_counterparty: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    by_asset_class: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])

    for row in rows:
        counterparty = _find_string(row, _COUNTERPARTY_KEYS, field="counterparty")
        asset_class = _find_string(row, _ASSET_CLASS_KEYS, field="asset_class")
        notional = _find_numeric(row, _NOTIONAL_KEYS, field="notional")
        prior_notional = _find_numeric(
            row,
            _PRIOR_NOTIONAL_KEYS,
            field="prior_notional",
            default=0.0,
        )

        by_counterparty[counterparty][0] += notional
        by_counterparty[counterparty][1] += prior_notional
        by_asset_class[asset_class][0] += notional
        by_asset_class[asset_class][1] += prior_notional

    records: list[dict[str, Any]] = []

    for name in sorted(by_counterparty, key=str.casefold):
        notional, prior_notional = by_counterparty[name]
        records.append(
            {
                "group_type": "counterparty",
                "group_name": name,
                "notional": notional,
                "prior_notional": prior_notional,
                "notional_change": notional - prior_notional,
            }
        )

    for name in sorted(by_asset_class, key=str.casefold):
        notional, prior_notional = by_asset_class[name]
        records.append(
            {
                "group_type": "asset_class",
                "group_name": name,
                "notional": notional,
                "prior_notional": prior_notional,
                "notional_change": notional - prior_notional,
            }
        )

    return _to_dataframe_or_records(records=records, columns=_TOTAL_COLUMNS)


def compute_notional_breakdown(exposures_df: Any) -> dict[str, float]:
    """Return asset-class notional fractions for the supplied exposure rows."""

    rows = _iter_rows(exposures_df, arg_name="exposures_df")
    if not rows:
        return {}

    by_asset_class: dict[str, float] = defaultdict(float)
    for row in rows:
        asset_class = _find_string(row, _ASSET_CLASS_KEYS, field="asset_class")
        notional = _find_numeric(row, _NOTIONAL_KEYS, field="notional")
        by_asset_class[asset_class] += notional

    total_notional = sum(by_asset_class.values())
    if total_notional == 0.0:
        return dict.fromkeys(sorted(by_asset_class, key=str.casefold), 0.0)

    return {
        name: by_asset_class[name] / total_notional
        for name in sorted(by_asset_class, key=str.casefold)
    }


def top_exposures(exposures_df: Any, n: int = 10) -> Any:
    """Return top-N exposures sorted by descending notional with deterministic ties."""

    if n <= 0:
        raise ValueError("n must be positive")

    rows = _iter_rows(exposures_df, arg_name="exposures_df")
    normalized_rows: list[dict[str, Any]] = []

    for row in rows:
        normalized_rows.append(
            {
                "counterparty": _find_string(row, _COUNTERPARTY_KEYS, field="counterparty"),
                "asset_class": _find_string(row, _ASSET_CLASS_KEYS, field="asset_class"),
                "notional": _find_numeric(row, _NOTIONAL_KEYS, field="notional"),
            }
        )

    normalized_rows.sort(
        key=lambda item: (
            -abs(float(item["notional"])),
            str(item["counterparty"]).casefold(),
            str(item["asset_class"]).casefold(),
        )
    )

    return _to_dataframe_or_records(records=normalized_rows[:n], columns=_TOP_EXPOSURE_COLUMNS)


def top_changes(totals_df: Any, n: int = 10) -> Any:
    """Return top-N absolute notional movers from totals output."""

    if n <= 0:
        raise ValueError("n must be positive")

    rows = _records_from_table(totals_df, arg_name="totals_df")
    change_rows: list[dict[str, Any]] = []

    for row in rows:
        if "notional_change" in row:
            try:
                change_value = float(row["notional_change"])
            except (TypeError, ValueError) as exc:
                raise ValueError("totals_df notional_change values must be numeric") from exc
        else:
            notional = _find_numeric(row, ("notional",), field="notional", default=0.0)
            prior_notional = _find_numeric(
                row,
                ("prior_notional",),
                field="prior_notional",
                default=0.0,
            )
            change_value = notional - prior_notional

        group_type = str(row.get("group_type", "")).strip() or "unknown"
        group_name = str(row.get("group_name", "")).strip() or "unknown"

        change_rows.append(
            {
                "group_type": group_type,
                "group_name": group_name,
                "notional": float(row.get("notional", 0.0) or 0.0),
                "prior_notional": float(row.get("prior_notional", 0.0) or 0.0),
                "notional_change": change_value,
                "absolute_change": abs(change_value),
            }
        )

    change_rows.sort(
        key=lambda item: (
            -float(item["absolute_change"]),
            str(item["group_type"]).casefold(),
            str(item["group_name"]).casefold(),
        )
    )

    return _to_dataframe_or_records(records=change_rows[:n], columns=_TOP_CHANGE_COLUMNS)


def compute_concentration_metrics(
    exposures_df: Any,
    group_by: list[str] | None = None,
) -> Any:
    """Compute Top 5 share, Top 10 share, and HHI per group.

    For each combination of *group_by* values the function computes:

    * **top5_share** – sum of the five largest entity notionals divided by the
      total group notional.  When the group has fewer than five entities, all
      entities are summed (i.e. top5_share == 1.0).
    * **top10_share** – same as above using ten entities.
    * **hhi** – Herfindahl-Hirschman Index: sum of squared market-share
      fractions for every entity in the group.  Ranges from 1/N (perfectly
      dispersed) to 1.0 (fully concentrated in one entity).

    When the total notional for a group is zero all three metrics are returned
    as ``0.0``.

    Parameters
    ----------
    exposures_df:
        Table of exposures.  Each row must include every column named in
        *group_by* and a notional column (resolved via the standard notional
        aliases: ``notional``, ``exposure``, ``total``, ``amount``).
    group_by:
        Column names to group on.  Defaults to ``["variant", "segment"]``.

    Returns
    -------
    Table with columns: *group_by columns* then ``top5_share``,
    ``top10_share``, ``hhi``.  The return type is a
    :class:`pandas.DataFrame` when pandas is available, otherwise a list of
    dicts.

    Raises
    ------
    ValueError
        If a required group_by column is absent from any row, or if a
        notional value cannot be converted to float.
    TypeError
        If *exposures_df* is not a DataFrame-like object or an iterable of
        row mappings.
    """
    if group_by is None:
        group_by = list(_CONCENTRATION_GROUP_COLUMNS)

    rows = _iter_rows(exposures_df, arg_name="exposures_df")

    if rows:
        sample = rows[0]
        missing = [col for col in group_by if col not in sample]
        if missing:
            raise ValueError(
                f"exposures_df is missing required group_by column(s): "
                f"{', '.join(repr(c) for c in missing)}"
            )

    groups: dict[tuple[str, ...], list[float]] = defaultdict(list)
    group_key_order: list[tuple[str, ...]] = []
    seen_keys: set[tuple[str, ...]] = set()

    for row in rows:
        key = tuple(str(row.get(col, "")).strip() for col in group_by)
        notional = _find_numeric(row, _NOTIONAL_KEYS, field="notional")
        if key not in seen_keys:
            group_key_order.append(key)
            seen_keys.add(key)
        groups[key].append(notional)

    records: list[dict[str, Any]] = []
    for key in group_key_order:
        notionals = sorted(groups[key], reverse=True)
        total = sum(notionals)

        if total == 0.0:
            top5_share = 0.0
            top10_share = 0.0
            hhi = 0.0
        else:
            top5_share = sum(notionals[:5]) / total
            top10_share = sum(notionals[:10]) / total
            hhi = sum((n / total) ** 2 for n in notionals)

        record: dict[str, Any] = {}
        for col, val in zip(group_by, key, strict=False):
            record[col] = val
        record["top5_share"] = top5_share
        record["top10_share"] = top10_share
        record["hhi"] = hhi
        records.append(record)

    output_columns = tuple(group_by) + _CONCENTRATION_METRIC_COLUMNS
    return _to_dataframe_or_records(records=records, columns=output_columns)


def write_concentration_metrics_csv(metrics: Any, path: Path | str) -> None:
    """Write concentration metrics to a CSV file.

    Parameters
    ----------
    metrics:
        Return value of :func:`compute_concentration_metrics` (DataFrame or
        list of dicts).
    path:
        Destination file path.  Parent directories are created if absent.
    """
    rows = _iter_rows(metrics, arg_name="metrics")
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        out_path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
