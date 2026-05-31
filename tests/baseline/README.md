# Counter_Risk app behavior baseline kit

Scenario-driven wiring / sensibility / regression tests built on the shared
**`baseline_kit`** package. Only the app-specific pieces live here.

## Requires

`baseline_kit` (the shared core) must be importable. It lives in
`stranske/Workflows` under `packages/app-baseline-kit`:

```bash
pip install "app-baseline-kit @ git+https://github.com/stranske/Workflows.git#subdirectory=packages/app-baseline-kit"
```

It is declared in this repo's `pyproject.toml` `[project.optional-dependencies]
dev`, so `pip install -e ".[dev]"` pulls it (plus `pytest-regressions`, which
needs `numpy` + `pandas`).

## Target surface

The **deterministic compute**
`counter_risk.compute.rollups.compute_concentration_metrics` — reduces an
exposure table to per-`(variant, segment)` concentration scalars
(`top5_share`, `top10_share`, `hhi`) with no DB / network / LLM. Field
definitions and the HHI scaling are in `docs/concentration_metrics.md`.

## Layout

```
adapter.py                # exposure fixture + patch -> flat metrics dict (the only app glue)
catalog.yaml              # base exposure table + scenario patches + directional checks
invariants.py             # economic bounds -> baseline_kit.InvariantResult
test_golden.py            # golden master of each scenario's flattened metrics
test_directional.py       # metamorphic checks (concentrate -> HHI up, disperse -> down...)
test_invariants.py        # invariants on base + every scenario
test_coverage_manifest.py # metric-key coverage -> docs/reports/baseline-coverage.md
```

## Scenario model

A *scenario* is the base exposure table (`catalog.yaml` `base.exposures`) with
an optional ordered `patch` applied. The patch DSL (`adapter.apply_patch`)
supports `set_notional`, `scale_notional`, `add_row`, `drop_counterparty`,
`zero_segment`, `keep_only` — enough to make each variant directionally
predictable (shift mass onto one name → more concentrated; spread it → more
dispersed).

## Running

```bash
pytest tests/baseline/                                   # full suite
pytest tests/baseline/test_golden.py --force-regen       # re-bless after an intended change
BASELINE_REFRESH_REPORT=1 pytest tests/baseline/test_coverage_manifest.py  # refresh report
```

## Invariants enforced

For every `(variant, segment)` group, grounded in `docs/concentration_metrics.md`:

- `0 <= top5_share <= 1`, `0 <= top10_share <= 1`, `0 <= hhi <= 1`
- `top5_share <= top10_share` (top-10 window ⊇ top-5 window)
- `hhi >= 1/N` for `N` positive-notional entities (1/N = perfect dispersion)
- single positive-notional entity ⇒ all three = 1.0
- ≤5 entities ⇒ `top5_share == 1.0`; ≤10 entities ⇒ `top10_share == 1.0`
- zero-total group ⇒ all three = 0.0
