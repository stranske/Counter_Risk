# Audit: calc-core (economic core)

Summary line: The calculations are largely correct and well-documented for the **non-negative-notional** case, with careful NaN/blank/division-by-zero handling in `futures_delta` and `limits`. The main numeric-correctness risk is **mixed-sign (short) notionals**: `compute_concentration_metrics` (HHI / Top5 / Top10) is mathematically wrong when any notional is negative, and it is inconsistent with the rest of the subsystem (`top_exposures`, `check_limits`), which deliberately use `abs()`. Secondary risks: silent NaN propagation into WAL via the parser, and an unused `px_date` parameter in WAL.

Files reviewed:
- `src/counter_risk/calculations/wal.py`
- `src/counter_risk/compute/rollups.py` (totals, breakdown, top_exposures, top_changes, risk proxies, concentration/HHI)
- `src/counter_risk/compute/limits.py`
- `src/counter_risk/compute/futures_delta.py`
- `src/counter_risk/compute/errors.py`, `__init__.py`
- Supporting: `src/counter_risk/parsers/exposure_maturity_schedule.py` (`_coerce_float`)

## Code Quality Findings

### [BLOCKER] HHI and Top-N shares are wrong for mixed-sign notionals
`src/counter_risk/compute/rollups.py:576-586`

`compute_concentration_metrics` sorts raw notionals descending and computes:
- `top5_share = sum(notionals[:5]) / total`
- `hhi = sum((n / total) ** 2 for n in notionals)`

When notionals can be negative (short futures positions are clearly in-scope — `top_exposures` line 384 and `check_limits` line 195/210 both use `abs()`), this produces economically meaningless results:

Verified empirically with rows `notional = 100` and `notional = -99` (same group):
```
top5_share = 1.0   top10_share = 1.0   hhi = 19801.0
```
HHI is defined on `[1/N, 1]` but here returns 19801 because `total` (=1) is a near-cancellation residual and each `(n/total)**2` blows up. Top5/Top10 also mis-rank: a large *negative* exposure sorts to the bottom and is excluded from the "top," even though it represents large concentration in absolute terms.

Recommendation: decide the intended economic convention and apply it consistently. Most likely fix: rank and weight by `abs(notional)` (matching `top_exposures`/`check_limits`), i.e. sort by `abs`, and compute shares/HHI over `sum(abs(notionals))`. If negative notionals are truly impossible for the concentration input, validate/reject them explicitly instead of silently producing bad numbers. Add a near-zero-total guard so tiny residual totals do not explode HHI.

### [MAJOR] Sign/`abs` convention is inconsistent across the subsystem
`rollups.py:384` (`top_exposures` uses `-abs(...)`), `rollups.py:576` (`compute_concentration_metrics` uses raw value), `limits.py:195,210` (`check_limits` uses `abs(...)`).

Three functions in the same package treat sign three-ways. Even if each is individually "intended," the divergence is a latent correctness trap and makes outputs hard to reconcile (e.g. a counterparty can be a top exposure but contribute "negatively" to its concentration group). Recommendation: document and centralize the notional-magnitude convention (single helper) so all rollup/concentration/limit math agrees.

### [MAJOR] Silent NaN propagation into WAL via parser `_coerce_float`
`src/counter_risk/parsers/exposure_maturity_schedule.py:96-99` and `calculations/wal.py:30-35`

`_coerce_float` returns `float(value)` for any `int|float` without a NaN check (only `None`, blanks, and `"-"/"N/A"` map to 0.0). A genuine `float('nan')` cell (common from xlsx/pandas) flows straight into `current_exposure`/`years_to_maturity`. `calculate_wal` then computes `sum(... )/total_exposure`; a NaN weight makes `total_exposure` NaN (the `== 0` guard at wal.py:31 does not catch NaN), so WAL silently becomes `nan`. Contrast `futures_delta._extract_notional` (lines 496-510) which explicitly rejects NaN. Recommendation: reject or zero NaN/inf in `_coerce_float`, or guard `total_exposure` with `math.isfinite` in `calculate_wal`.

### [MAJOR] WAL ignores `px_date` entirely
`calculations/wal.py:16,26` (and `_coerce_px_date` at 46-56)

`calculate_wal(exposure_summary_path, px_date)` coerces `px_date` and then never uses it; `years_to_maturity` is read directly from the workbook (parser lines 158-160, 175). The docstring (lines 19-24) does not mention px_date either. This is either dead parameter surface or a missing requirement: if the spreadsheet stores maturity *dates* in some inputs, WAL should derive `years_to_maturity` from `px_date`; if it always stores precomputed years, the parameter is misleading. The caller `workflows/historical_update.py:35` passes it. Recommendation: either remove the parameter (and the import of `_coerce_px_date` there) or wire it into the maturity computation. At minimum document that it is accepted for interface symmetry and intentionally unused.

### [MINOR] WAL gives no signal when total exposure is negative
`calculations/wal.py:31-35`

Only `total_exposure == 0` is special-cased. A net-negative `total_exposure` (possible if exposures can be signed) yields a ratio that is arithmetically defined but not a meaningful "average life." Likely fine if exposures here are always non-negative, but worth an explicit assertion/guard for robustness.

### [MINOR] `check_limits` percentage limit denominator can mask concentration
`limits.py:218-220`

Percentage-of-total uses `matched_abs_notional / total_abs_notional` over all rows. This is reasonable, but note that exactly meeting a limit is not a breach (`breach_amount <= 0.0` skip at line 223) — correct, just confirm operators expect ">" not ">=" semantics. Documented here for completeness, not a defect.

### [MINOR] Concentration/risk-proxy paths do not reject inf
`rollups.py:568,586` and `586`

`_find_numeric` accepts `float('inf')`; `apply_repo_cash_to_totals` checks `math.isfinite` (line 274) but the concentration/totals/proxy paths do not. An inf notional would propagate to HHI/shares. Low likelihood from clean inputs; add a finite check in `_find_numeric` for defense in depth.

## Duplication / Simplification Opportunities

### [MINOR] `_iter_rows` / `_is_dataframe_like` / `_to_dataframe_or_records` duplicated across modules
`rollups.py:72-93,130-142`, `limits.py:34-69`, `futures_delta.py:322-341,528-539`

Three near-identical implementations of: DataFrame-or-iterable row coercion, mapping validation, and "DataFrame when pandas available else list-of-dicts" output. `limits._to_dataframe_or_records` differs only in default fill (`None` vs `0.0`) and a `notes` column fixup. Recommendation: extract a small shared `compute/_tables.py` with `iter_rows(...)` and `to_table(records, columns, *, fill=...)`. Reduces ~120 lines and removes the risk of the three copies drifting (which is partly how the `abs`/sign inconsistency above arose).

### [MINOR] Numeric extraction helpers overlap
`rollups._find_numeric` (104-127), `limits._find_notional` (81-94), `futures_delta._extract_notional` (421-525)

Three different "pull a float out of aliased keys, handle blank/None/non-numeric" routines with subtly different policies (rollups raises, limits raises, futures returns 0.0 + warns, only futures checks NaN). Consolidating onto one parameterized helper (`strict`, `nan_policy`, `default`) would unify NaN handling and close the WAL NaN gap by construction.

### [MINOR] Repeated `sorted(..., key=str.casefold)` and tie-break sort keys
`rollups.py:208,220,356,360` and the multi-field sort keys at `rollups.py:382-388,432-438`, `limits.py:171-176,239-245`

Consistent deterministic-ordering pattern; fine as-is, but a tiny `_casefold_key` helper would de-duplicate and document intent.

## Notable Strengths

- `futures_delta._extract_notional` is exemplary: explicit handling of None, blank string, non-numeric, and NaN, with structured warning codes and an optional strict mode (lines 455-525).
- Division-by-zero is correctly guarded everywhere it matters: WAL (`wal.py:31`), notional breakdown (`rollups.py:355`), concentration total==0 (`rollups.py:579`), percentage limits (`limits.py:219`).
- Deterministic, well-specified output ordering with documented stable-sort tie-breaks (`futures_delta.py:278-280`, `rollups.py:382-388`).
- Graceful pandas-optional design (`_to_dataframe_or_records` / `_to_output`) so calculations work without pandas installed.
- Concentration semantics (Top5/Top10 < N entities, HHI range) are clearly documented in the docstring (`rollups.py:505-547`) and `_coerce_float` handles accounting formats like `(123)` negatives and `$`/comma stripping (`exposure_maturity_schedule.py:104-107`).
- `apply_repo_cash_to_totals` validates finiteness and empty keys of injected cash amounts (`rollups.py:264-275`).
