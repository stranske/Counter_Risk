"""App-specific adapter for Counter_Risk concentration metrics.

This is the ONLY app-specific piece the shared ``baseline_kit`` needs: a way to
turn an input (here, an exposure-table fixture plus a scenario *patch*) into a
flat dict of named scalar metrics. Everything else -- directional checks,
invariants, golden masters, the coverage manifest -- is generic and lives in
``baseline_kit``.

The deterministic compute surface is
``counter_risk.compute.rollups.compute_concentration_metrics`` (no DB, no
network, no LLM), so baselines here are stable.

Scenario model
--------------
The base exposure table lives in ``catalog.yaml`` under ``base.exposures``.
Each *scenario* is the base table with an optional ``patch`` applied. A patch is
an ordered list of operations -- the small DSL ``apply_patch`` understands:

* ``{op: set_notional, counterparty: X, segment: S, value: V}`` -- overwrite the
  notional of a single (segment, counterparty) row.
* ``{op: scale_notional, counterparty: X, segment: S, factor: F}`` -- multiply.
* ``{op: add_row, variant: ..., segment: ..., counterparty: ..., notional: ...}``
  -- append a new exposure row.
* ``{op: drop_counterparty, counterparty: X, segment: S}`` -- remove matching rows.
* ``{op: zero_segment, segment: S}`` -- set every notional in a segment to 0.
* ``{op: keep_only, counterparty: X, segment: S}`` -- keep only that row in the
  segment (collapse to a single entity).

This keeps the catalog declarative and the variants directionally predictable
(shift mass onto one name -> more concentrated; spread it out -> more dispersed).

Metric flattening
-----------------
``compute_concentration_metrics`` returns one row per ``(variant, segment)``
group with ``top5_share``/``top10_share``/``hhi``. We flatten each group to keys
``"<variant>.<segment>.<metric>"`` so the whole run is one flat ``dict[str,
float]`` -- exactly what ``baseline_kit`` golden/directional/coverage machinery
consumes.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

# The metric names this surface produces per group (the kit's coverage "input
# parameter" space at the metric level).
METRIC_NAMES = ("top5_share", "top10_share", "hhi")

GROUP_BY = ["variant", "segment"]


# ---------------------------------------------------------------------------
# Patch DSL
# ---------------------------------------------------------------------------


def _matches(row: dict[str, Any], counterparty: str | None, segment: str | None) -> bool:
    if counterparty is not None and row.get("counterparty") != counterparty:
        return False
    if segment is not None and row.get("segment") != segment:
        return False
    return True


def apply_patch(
    base_rows: list[dict[str, Any]], patch: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """Return a deep copy of ``base_rows`` with ``patch`` operations applied."""
    rows = copy.deepcopy(base_rows)
    for step in patch or []:
        op = step["op"]
        seg = step.get("segment")
        cp = step.get("counterparty")
        if op == "set_notional":
            for r in rows:
                if _matches(r, cp, seg):
                    r["notional"] = float(step["value"])
        elif op == "scale_notional":
            factor = float(step["factor"])
            for r in rows:
                if _matches(r, cp, seg):
                    r["notional"] = float(r["notional"]) * factor
        elif op == "add_row":
            rows.append(
                {
                    "variant": step["variant"],
                    "segment": step["segment"],
                    "counterparty": step["counterparty"],
                    "notional": float(step["notional"]),
                }
            )
        elif op == "drop_counterparty":
            rows = [r for r in rows if not _matches(r, cp, seg)]
        elif op == "zero_segment":
            for r in rows:
                if _matches(r, None, seg):
                    r["notional"] = 0.0
        elif op == "keep_only":
            rows = [
                r
                for r in rows
                if (seg is not None and r.get("segment") != seg) or _matches(r, cp, seg)
            ]
        else:  # pragma: no cover - guards against catalog typos
            raise ValueError(f"unknown patch op: {op!r}")
    return rows


# ---------------------------------------------------------------------------
# Compute + flatten
# ---------------------------------------------------------------------------


def _as_records(table: Any) -> list[dict[str, Any]]:
    if hasattr(table, "to_dict"):
        return list(table.to_dict(orient="records"))
    return [dict(row) for row in table]


def run_scenario(scenario: dict[str, Any], base_rows: list[dict[str, Any]]) -> dict[str, float]:
    """Apply a scenario's patch to the base table, compute metrics, flatten.

    Returns a flat ``dict`` keyed ``"<variant>.<segment>.<metric>"`` -> float.
    Deterministic: ``compute_concentration_metrics`` sorts notionals and emits
    groups in first-seen key order, so the flattened dict is stable.
    """
    from counter_risk.compute.rollups import compute_concentration_metrics

    rows = apply_patch(base_rows, scenario.get("patch"))
    result = compute_concentration_metrics(rows, group_by=list(GROUP_BY))

    flat: dict[str, float] = {}
    for rec in _as_records(result):
        variant = rec["variant"]
        segment = rec["segment"]
        for metric in METRIC_NAMES:
            flat[f"{variant}.{segment}.{metric}"] = float(rec[metric])
    return flat


def metric_names() -> list[str]:
    return list(METRIC_NAMES)
