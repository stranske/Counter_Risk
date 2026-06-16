# Functionality & Parameter Wiring Audit

Summary line: Most parameters are correctly loaded, validated, and wired to economically-correct consumers (limits, HHI, series inclusion, reconciliation all move outputs in the right direction). One BLOCKER: the `percent_of_total` limit denominator is built from a mixed-granularity row set, so clearing-house / segment percentage limits are silently diluted by counterparty-totals notional and will under-report breaches.

## Summary

- Config loaders (`config.py`, `limits_config.py`, `name_registry.py`) are strict Pydantic models with `extra="forbid"`, duplicate-key rejection, and good validation. Loading is sound.
- `limits.yml` is fully wired end-to-end: `load_limits_config` -> `find_missing_limit_entities` + `check_limits` in `pipeline/run.py:2270-2286`. Direction verified by spot-check: tightening `limit_value` produces breaches, loosening removes them, for both `absolute_notional` and `percent_of_total`. `enabled: false` correctly excludes entries; `strict_missing_entities: true` raises (run.py:2275).
- `name_registry.yml` `series_included` / `by_segment` flags are wired through `normalize.counterparty_included_for_variant` (normalize.py:261-293) with correct precedence (segment override -> variant flag -> default-include).
- HHI / Top-5 / Top-10 concentration (`compute_concentration_metrics`) is wired at run.py:2191 and is economically correct (concentrated HHI 0.815 vs dispersed 0.10 on synthetic input).
- `reconciliation.fail_policy` is wired (run.py:3679, 3756, 3763): `strict` raises, `warn` only records findings — correct direction.
- The `as_of_date` / variant input-path parameters (`mosers_*_xlsx`, `hist_*_xlsx`, `monthly_pptx`, `output_root`) are consumed; `output_root` differentiates the three variant configs (`runs/all_programs`, `runs/ex_trend`, `runs/trend`).

The one material defect is in how the limit-evaluation exposure row set is assembled, which corrupts the `percent_of_total` denominator.

## Parameter Wiring Map

| param | file | consumer | direction-check | status |
|-------|------|----------|-----------------|--------|
| `limits[].limit_value` | limits.yml | `check_limits` (compute/limits.py:222) via run.py:2286 | tighter -> more breaches (verified) | OK |
| `limits[].limit_kind` (absolute_notional) | limits.yml | compute/limits.py:215-216 | OK; matched notional vs threshold | OK |
| `limits[].limit_kind` (percent_of_total) | limits.yml | compute/limits.py:218-220 (global denom L195) | **denominator mixes granularities** | **BLOCKER** |
| `limits[].entity_type` | limits.yml | `_ENTITY_COLUMN_ALIASES` (compute/limits.py:25-31) | aliases resolve per type | OK |
| `limits[].entity_name` | limits.yml | canonicalized match (limits.py:46-52, 207) | OK | OK |
| `limits[].severity` (fail/warning) | limits.yml | run.py:2295-2299 -> manifest + GUI banner (gui/runner.py:227) | reported, does NOT halt run | MAJOR (expectation gap) |
| `limits[].enabled` | limits.yml | skipped if false (limits.py:160,191) | OK | OK |
| `strict_missing_entities` | limits.yml | run.py:2275 raises | true -> hard fail | OK |
| `schema_version` | limits.yml / name_registry.yml | `Literal[1]` gate | OK | OK |
| `entries[].canonical_key/aliases/display_name` | name_registry.yml | normalize.py resolution + dedupe | OK | OK |
| `series_included.{all_programs,ex_trend,trend}` | name_registry.yml | normalize.py:287-292 | false -> excluded from variant | OK |
| `series_included.by_segment` | name_registry.yml | normalize.py:283-285 | segment override wins | OK |
| `reconciliation.fail_policy` | all_programs/ex_trend/trend/fixture_replay.yml | run.py:3679,3763 | strict -> raise | OK |
| `reconciliation.expected_segments_by_variant` | (config default) | run.py:3678 | passed to reconciler | OK |
| `as_of_date` | all variant ymls | dates / run plumbing (22 files) | OK | OK |
| `mosers_*_xlsx`, `hist_*_xlsx`, `monthly_pptx` | all variant ymls | parsers / pipeline inputs | OK | OK |
| `output_root` | all variant ymls | run output dir | distinct per variant | OK |
| `cash_total_min` / `cash_total_max` | (config only) | run.py:1197,1214 | bound checks | OK (not in shipped yml) |
| `required_repo_counterparties` | (config only) | run.py:1165 | OK | OK |
| `include_concentration_table_in_ppt` | (config only) | run.py:624 | OK | OK |
| `output_generators[].{stage,enabled}` | (config default) | run.py:3317-3334 registry.load | OK | OK |
| `enable_llm_logging` (WorkflowConfig) | (config only) | **none** | never read off WorkflowConfig | MINOR (dead) |

## Mis-wired or Dead Parameters

### [BLOCKER] `percent_of_total` limits diluted by mixed-granularity denominator
- `compute/limits.py:195` computes a single global `total_abs_notional = sum(abs(notional) for every row)`.
- `pipeline/run.py:2206-2254` (`_build_limit_exposure_rows`) builds the row set by concatenating two different granularities into one list:
  - counterparty-level rows from `parsed["totals"]` (carry `counterparty` + `notional`), and
  - futures-level rows from `parsed["futures"]` (carry `clearing_house`/`fcm`/`segment`/`custom_group` + `notional`), with NO `counterparty` field.
- Consequence: a `clearing_house` `percent_of_total` limit (e.g. the shipped `cme` 0.35 cap) divides CME futures notional by the sum of *all counterparty totals plus all futures*. Spot-check: with CME=40 of 100 futures but 1000 of counterparty totals, the CME share is computed as 40/1100 = 3.6% instead of the intended 40%, so a real 40% concentration does NOT breach the 35% limit.
- The same dilution affects `segment` and `custom_group` percent limits. Counterparty `percent_of_total` limits are inversely affected (their denominator is inflated by futures rows from a different base).
- Not caught by tests: `tests/compute/test_limits.py` only feeds homogeneous row sets; nothing exercises `_build_limit_exposure_rows` -> `check_limits` together.
- Fix direction: compute `percent_of_total` against a denominator scoped to the same `entity_type` / granularity (e.g. only futures rows for clearing_house/fcm/segment, only counterparty rows for counterparty), or tag rows with their source base and restrict the denominator accordingly.

### [MINOR] `WorkflowConfig.enable_llm_logging` is dead
- Defined at `config.py:118` but never read from any `WorkflowConfig` instance (grep finds zero `config.enable_llm_logging` reads). The chat artifact gate uses `ChatSession.enable_llm_logging` (`chat/session.py:227,316`), a separate field set by its own default — not fed from `WorkflowConfig`. The YAML files do not set it, so behavior is unaffected, but the field is misleading.

### [MINOR/by-design] `custom_group` / `segment` futures dimensions depend on parser output
- `_build_limit_exposure_rows` only emits `custom_group` if the parsed futures records contain a `custom_group`/`group` column (run.py:2244-2245). If the futures parser never emits those, a `custom_group` limit can only ever be reported "missing," never matched. The shipped `staged_policy_example` entry is `enabled: false`, so no current impact, but enabling it without confirming the parser emits the column would yield a permanent false "missing entity" warning.

## Economic-Sensibility Concerns

1. **`severity: fail` does not fail the run.** A `fail` limit breach (limits.yml:33, the Citibank 250M cap) is written to `limit_breaches.csv`, counted in `fail_breach_count`, surfaced as a GUI banner (gui/runner.py:227) and manifest field, but the pipeline still completes successfully with no nonzero exit (run.py:537-548 only re-raises on internal errors, not on breaches). By contrast `strict_missing_entities` and reconciliation `fail_policy: strict` both raise. An operator reading the limits.yml schema comment ("severity ... operator escalation level: warning | fail") could reasonably expect `fail` to abort or exit nonzero. Direction is defensible as report-only, but the asymmetry with the other two "fail/strict" knobs is a usability gap (MAJOR).

2. **HHI scaling is correct.** Verified `sum((n/total)**2)`; ranges 1/N to 1.0; concentrated input gives higher HHI. Top-5/Top-10 shares are `min(N,5)`/`min(N,10)` sums over total, correct, and clamp to 1.0 for small groups as documented.

3. **Limit `absolute_notional` and `percent_of_total` thresholds otherwise move outputs in the correct direction** (verified by spot-check at both kinds): tighter threshold -> breach appears, looser -> breach disappears, breach_amount = actual - limit.

4. **`series_included` / `by_segment` direction correct:** setting a flag `false` excludes the series from that variant's expected-coverage reconciliation (normalize.py:287-292); the shipped `ice_euro` `trend: false` + `by_segment.trend.futures: false` correctly suppresses it for Trend.
