# Concentration Metrics Output

Each pipeline run writes a `concentration_metrics.csv` file into the run folder
and surfaces a parallel summary under the `concentration_metrics` key in
`manifest.json`. This document defines those output fields, the HHI scaling
used, and how operators should interpret the values.

## Where the outputs land

- `<run_dir>/concentration_metrics.csv` — flat table, one row per
  `(variant, segment)` group.
- `<run_dir>/manifest.json` — same records under
  `manifest["concentration_metrics"]`. The CSV and the manifest summary are
  written from the same in-memory result, so a value mismatch indicates a bug
  rather than expected drift.
- Distribution PPT (optional) — when
  `include_concentration_table_in_ppt: true` is set in the workflow config,
  the same records are appended as a native PPTX table on a new slide of the
  distribution PPT. The toggle defaults to `false`; absence or disablement
  must not change CSV/manifest contents.

## CSV columns

| Column | Type | Meaning |
| --- | --- | --- |
| `variant` | string | Pipeline variant the row belongs to (e.g., `all_programs`, `ex_llc`, `llc`). One row per variant per segment. |
| `segment` | string | Asset-class slice within the variant. Individual asset classes (`TIPS`, `Treasury`, `Equity`, `Commodity`, `Currency`, `Cash`) plus the synthetic `total` segment, which aggregates the per-counterparty `Notional` column across all asset classes. |
| `top5_share` | float in `[0.0, 1.0]` | Fraction of group notional concentrated in the five largest counterparties in the group. When the group has fewer than five counterparties, all counterparties are summed and the value is `1.0`. |
| `top10_share` | float in `[0.0, 1.0]` | Same as `top5_share` but for the ten largest counterparties. Equals `top5_share` when the group has five or fewer counterparties. |
| `hhi` | float in `[0.0, 1.0]` | Herfindahl-Hirschman Index — see scaling note below. |

Row ordering is deterministic: groups appear in the order their
`(variant, segment)` keys are first encountered while iterating the parsed
exposure rows, which itself is deterministic for a given input set.

## HHI scaling

The HHI value reported here is the **sum of squared market-share fractions**:

```
hhi = Σ (counterparty_notional / group_total_notional) ** 2
```

This is the share-fraction form (range `[1/N, 1.0]` for `N` counterparties
contributing positive notional). It is **not** the U.S. DOJ "0–10,000" form
that scales by `100 ** 2`. To convert to the DOJ scale, multiply by 10,000.

Reference points on this scale:

- `hhi = 1.0` — entire group notional sits with one counterparty.
- `hhi ≈ 0.50` — comparable to two equally-sized counterparties.
- `hhi ≈ 0.25` — comparable to four equally-sized counterparties.
- `hhi ≈ 0.10` — comparable to ten equally-sized counterparties.

## Empty / zero-total handling

- A group whose total notional sums to `0.0` reports `top5_share = 0.0`,
  `top10_share = 0.0`, and `hhi = 0.0`. The row is still emitted so the
  `(variant, segment)` key remains visible in downstream consumers.
- A group with a single counterparty reports `top5_share = top10_share = 1.0`
  and `hhi = 1.0`.
- An empty exposure set produces an empty CSV (header-only or zero-byte,
  depending on row count) and omits the `concentration_metrics` key from the
  manifest.

## Operator interpretation

These metrics are intended to make single-name dependency visible without
operators having to inspect raw exposure tables. Suggested reading:

1. Scan the `total` segment first for each variant — that is the whole-portfolio
   concentration view.
2. A `top5_share` above roughly `0.60` in the `total` segment usually warrants
   a look at the per-counterparty rows in the totals output, because it
   indicates that more than half the variant's notional sits with five or
   fewer counterparties.
3. An `hhi` above roughly `0.18` (DOJ 1,800) is the conventional
   "concentrated market" threshold; above `0.25` (DOJ 2,500) is "highly
   concentrated." These cutoffs are heuristics for orientation, not policy
   limits.
4. Drill into individual asset-class segments (`TIPS`, `Treasury`, etc.) when
   the `total` view looks fine but a single asset class is dominated by one
   counterparty.

## Disabling or skipping

Concentration metrics are computed unconditionally as part of every pipeline
run; there is no flag to disable the CSV/manifest output. The
`include_concentration_table_in_ppt` config flag controls only whether the
optional PPT slide is appended to the distribution deliverable. Existing
report generation must continue to pass when downstream consumers do not
read the `concentration_metrics` key — readers should treat the key as
optional.
