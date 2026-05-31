"""Counter_Risk app behavior baseline kit.

Built on the shared ``baseline_kit`` package -- this directory contains only the
app-specific pieces (adapter, catalog, invariant bounds). The generic harness
(directional engine, invariant assertion, golden glue, coverage manifest) is
imported from ``baseline_kit``, the same core the TMP / PAEM / trip-planner
kits use.

Target surface: ``counter_risk.compute.rollups.compute_concentration_metrics``
-- a deterministic compute (no DB, no network, no LLM) that reduces an exposure
table to per-group concentration scalars (top5_share, top10_share, HHI).
"""
