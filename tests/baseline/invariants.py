"""Counter_Risk concentration-metric economic invariants.

These are properties that must hold for ANY exposure table, grounded in the
definitions in ``docs/concentration_metrics.md`` -- NOT generic placeholders:

  * shares are fractions:        0 <= top5_share <= 1, 0 <= top10_share <= 1
  * window monotonicity:         top5_share <= top10_share
                                 (the top-10 window is a superset of the top-5)
  * HHI is a fraction:           0 <= hhi <= 1
  * HHI floor for N positive
    entities:                    hhi >= 1/N - eps   (1/N is perfect dispersion)
  * single entity (or single
    positive-notional entity):   top5 = top10 = hhi = 1.0
  * zero-total group:            top5 = top10 = hhi = 0.0

The result type and assertion helper are shared
(``baseline_kit.InvariantResult`` / ``assert_invariants``).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from baseline_kit import InvariantResult

from . import adapter

_EPS = 1e-9


def _group_stats(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Per (variant, segment): list of notionals + derived counts/totals.

    Mirrors the surface's grouping (str-strip key, notional alias resolution is
    unnecessary here because the catalog uses the canonical ``notional`` key).
    """
    notionals: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in rows:
        key = (str(r["variant"]).strip(), str(r["segment"]).strip())
        notionals[key].append(float(r["notional"]))
    stats: dict[tuple[str, str], dict[str, Any]] = {}
    for key, vals in notionals.items():
        total = sum(vals)
        positive = [v for v in vals if v > 0]
        stats[key] = {
            "n_entities": len(vals),
            "n_positive": len(positive),
            "total": total,
        }
    return stats


def check_scenario(scenario: dict[str, Any], base_rows: list[dict[str, Any]]) -> list[InvariantResult]:
    """Run every invariant against one scenario's metrics."""
    rows = adapter.apply_patch(base_rows, scenario.get("patch"))
    metrics = adapter.run_scenario(scenario, base_rows)
    stats = _group_stats(rows)

    results: list[InvariantResult] = []

    def add(name: str, ok: bool, detail: str, severity: str = "error") -> None:
        results.append(InvariantResult(name, bool(ok), severity, detail))

    for (variant, segment), s in stats.items():
        prefix = f"{variant}.{segment}"
        top5 = metrics[f"{prefix}.top5_share"]
        top10 = metrics[f"{prefix}.top10_share"]
        hhi = metrics[f"{prefix}.hhi"]
        total = s["total"]
        n_pos = s["n_positive"]

        # Shares are fractions in [0, 1].
        add(f"{prefix}.top5_in_unit_interval", -_EPS <= top5 <= 1.0 + _EPS, f"top5={top5}")
        add(f"{prefix}.top10_in_unit_interval", -_EPS <= top10 <= 1.0 + _EPS, f"top10={top10}")
        # HHI is a fraction in [0, 1] (share-fraction form, not DOJ 0-10000).
        add(f"{prefix}.hhi_in_unit_interval", -_EPS <= hhi <= 1.0 + _EPS, f"hhi={hhi}")

        # Window monotonicity: top-10 window contains the top-5 window.
        add(
            f"{prefix}.top5_le_top10",
            top5 <= top10 + _EPS,
            f"top5={top5} top10={top10}",
        )

        if total <= 0:
            # Zero-total group: all three are 0.0 by definition.
            add(f"{prefix}.zero_total_all_zero",
                abs(top5) <= _EPS and abs(top10) <= _EPS and abs(hhi) <= _EPS,
                f"top5={top5} top10={top10} hhi={hhi}")
        else:
            # HHI floor: with N positive-notional entities, hhi >= 1/N
            # (equality iff perfectly even). Use positive count since zero-notional
            # entities contribute 0 share and don't raise the floor.
            floor = 1.0 / n_pos if n_pos else 0.0
            add(
                f"{prefix}.hhi_ge_one_over_n",
                hhi >= floor - _EPS,
                f"hhi={hhi} 1/N={floor} (N_positive={n_pos})",
            )

            if n_pos == 1:
                # A single positive-notional entity owns the whole group.
                add(
                    f"{prefix}.single_entity_all_one",
                    abs(top5 - 1.0) <= _EPS
                    and abs(top10 - 1.0) <= _EPS
                    and abs(hhi - 1.0) <= _EPS,
                    f"top5={top5} top10={top10} hhi={hhi}",
                )

            if s["n_entities"] <= 5:
                # Fewer than 5 entities -> the whole group fits the top-5 window.
                add(f"{prefix}.few_entities_top5_one", abs(top5 - 1.0) <= _EPS, f"top5={top5}")
            if s["n_entities"] <= 10:
                add(f"{prefix}.few_entities_top10_one", abs(top10 - 1.0) <= _EPS, f"top10={top10}")

    return results
