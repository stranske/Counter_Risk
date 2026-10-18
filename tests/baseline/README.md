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
adapter.py                   # exposure fixture + patch -> flat metrics dict (the only app glue)
catalog.yaml                 # base exposure table + scenario patches + directional checks
invariants.py                # economic bounds -> baseline_kit.InvariantResult
test_golden.py               # golden master of each scenario's flattened metrics
test_directional.py          # metamorphic checks (concentrate -> HHI up, disperse -> down...)
test_invariants.py           # invariants on base + every scenario
test_coverage_manifest.py    # metric-key coverage -> docs/reports/baseline-coverage.md
test_segment_dispersion.py   # hand-check shares + control-segment isolation (#1163)
```

## Scenario model

A *scenario* is the base exposure table (`catalog.yaml` `base.exposures`) with
an optional ordered `patch` applied. The patch DSL (`adapter.apply_patch`)
supports `set_notional`, `scale_notional`, `add_row`, `drop_counterparty`,
`zero_segment`, `keep_only` — enough to make each variant directionally
predictable (shift mass onto one name → more concentrated; spread it → more
dispersed).

### Segment top-share dispersion (issue #1163)

The base Treasury (3 names) and Equity (2 names) segments are saturated:
`top5_share` / `top10_share` are always `1.0`, so equality assertions on those
values do not prove sensitivity. Catalog scenarios `treasury_dispersed` and
`equity_dispersed` add enough positive-notional counterparties to cross both
cutoffs (`N > 10`) while leaving the other segments untouched. Hand-checkable
expected shares are documented in `catalog.yaml` and locked by
`test_segment_dispersion.py`. Four enforced directionals cover
`all_programs.{treasury,equity}.{top5_share,top10_share}`; all nine flat
concentration keys are listed under `priority_metrics`.

Observable verification (not production wiring instrumentation):

- Deleting any of the four segment-share directionals opens a
  `test_priority_metrics_covered` gap.
- Freezing a dispersed variant share at constant `1.0` fails its decrease
  directional (`test_constant_one_mutation_fails_segment_share_directional`).
- `docs/reports/baseline-coverage.md` reports **9 of 9** declared directional
  keys. The report's "Observed read at runtime: 0" line is expected: coverage
  here is catalog-declared, not a runtime-read probe of production code paths.

Compatibility preserved: existing golden CSVs for pre-#1163 scenarios are not
re-blessed; only new golden entries are added for the dispersion scenarios.
`compute_concentration_metrics` is unchanged.

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
