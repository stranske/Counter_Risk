## Summary

Preserve the issue #1218 coverage chunk on existing PR **#1232** and strengthen the first ranked target, the NISA parser. A dimensionless XLSX can end with a totals row rather than a section-stop label. The new EOF case verifies the final counterparty and its distinct notional survive parsing. It detects silent exposure loss when either the totals loop or the worksheet row bound excludes the last row. This follow-up changes no production behavior and claims **zero additional covered statements**.

The issue's checklist and baseline are stale: the whole non-slow suite on Python **3.14.9** already measured **95.8306%** before this follow-up. No new PR was opened. The original chunk's historical matched measurements reduced missing statements by **198**, against the issue's ~180-unit goal. Those older Python 3.12.2 numbers are preserved below, separately from current supported-interpreter results.

## Supported-interpreter validation (2026-11-05)

`python -m pytest tests/ -m "not slow" -n 4 --dist load --cov=counter_risk --cov-report=term --cov-report=json:<output> -q`

| Python 3.14.9 whole non-slow suite | Before EOF case | After EOF case |
|---|---:|---:|
| Passed / skipped | 3,053 / 1 | 3,054 / 1 |
| Covered / total statements | 11,722 / 12,232 | 11,722 / 12,232 |
| Line coverage | 95.8306% | 95.8306% |
| Time | 80.40s | 75.32s |

Targeted verification: `python -m pytest tests/test_nisa_all_programs_parser.py -m "not slow" --cov=counter_risk.parsers.nisa --cov-report=term-missing -q` → **37 passed**, **216/218 statements**, **Cover 99%**, versus 36 passed and the same coverage before. The two missing lines (240, 312) are counterparty-inference fallbacks that the public caller cannot reach with its required numeric headers. No invariant is bypassed to exercise them.

**Break-and-revert actually run:** `python -m pytest tests/test_nisa_all_programs_parser.py::test_parser_reads_workbook_without_dimension_record -m "not slow" -q`. Removing the totals loop's inclusive `+ 1` produced **1 failed (EOF), 1 passed (existing stop-marker case)**, exit 1; restoring source produced **2 passed**, exit 0. Independently changing the cached worksheet row bound to `int(max_row) - 1` produced the same red result; restoring source again produced **2 passed**. Both failures specifically omitted `Final Bank`. Full commands and results: `eof-mutation-receipts.json`. Production source was restored byte-for-byte.

Black 26.10.1 and Ruff 0.17.3 use the reusable CI flags. Black also required a mechanical reformat of three existing assertions in `tests/test_python_floor.py`; its **21 existing tests passed** afterward. Black checks passed for all **414 files** with `--check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .` and the CI exclusion variant adding `\.venv`. Ruff passed with `check --output-format github --extend-exclude .workflows-lib .`. A single Black worker and writable `/tmp` cache accommodate this sandbox; exact commands are recorded in `coverage-summary.json`.

Publication is blocked: local `git commit` cannot create `.git/index.lock` on the read-only `.git` directory, and automatic approval review rejected GitHub tree creation because the tool requires approval while policy is `never`. This report is prepared locally and has not been applied to the live PR body. Verified changes remain uncommitted; an apply-ready patch is saved at `/tmp/issue-1218-verified.patch`. Hosted verification of this follow-up remains pending until publication. Historical Gate run [41974656827](https://github.com/stranske/Counter_Risk/actions/runs/41974656827) verified Python 3.13 and 3.14 at `ab025f3e`; it does **not** verify the current test change. Previous source revision `4c08e8b` is the verification base for this follow-up, not a self-referential claim about the resulting commit.

## Historical coverage comparison

The issue cites blended line+branch coverage, but repository configuration measures **lines only** (`branch=false`). Gate PR runs have coverage disabled; local matched whole-suite coverage supplies the before/after evidence. The following original Python **3.12.2** measurements compare historical base `faad152` to the earlier coverage chunk: **10,911/12,216 (89.3173%) → 11,109/12,216 (90.9381%)**, **198 fewer missing statements**. Do not treat them as current Python 3.14 measurements or as the incremental gain of PR #1232 relative to today's main.

| Target (issue order) | Historical missing before | Missing after | Historical before % | After % |
|---|---:|---:|---:|---:|
| parsers/nisa.py | 30 | 2 | 86.24% | 99.08% |
| compute/rollups.py | 16 | 0 | 94.86% | 100.00% |
| runner_launch.py | 14 | 0 | 92.75% | 100.00% |
| cli/mapping_diff_report.py | 12 | 1 | 87.76% | 98.98% |
| reports/mapping_diff.py | 12 | 0 | 87.88% | 100.00% |
| chat/providers/langchain_runtime.py | 9 | 2 | 96.17% | 99.15% |
| normalize.py | 5 | 0 | 95.54% | 100.00% |
| limits_config.py | 3 | 0 | 94.74% | 100.00% |
| chat/providers/base.py | 2 | 2 | 98.77% | 98.77% |
| ppt/pptx_postprocess.py | 54 | 0 | 66.46% | 100.00% |
| build/xlsm.py | 48 | 0 | 60.33% | 100.00% |

The supported Python 3.14 whole-suite run reproduced every target's "after" coverage shown above; per-target before/after data for this follow-up are in `coverage-summary.json` under `eof_followup`. Historical missing units are retained as the issue's original baseline; whole-suite totals differ across interpreters and the expanded suite. Seven statements remain: two NISA inference fallbacks, one CLI empty-payload fallback, two runtime empty-catalog fallbacks, and two repeated provider missing-environment checks. The existing public contracts prevent these paths; no padding tests were added to force them. The original ~180-unit goal is exceeded by 18 statements in the historical comparison; this follow-up adds behavioral discrimination only.

## Production fix and prior mutation evidence

The earlier chunk's sole production fix reorders NISA's specific `notional_change` aliases ahead of generic `notional`: when a change column precedes Notional, substring matching otherwise consumes it as Notional and rejects the workbook. The two XLSX regression cases for `Notional Change` and `Notional Change From Prior Month` fail with the original order (**2 failed**, exit 1) and pass after restoration (**2 passed**, exit 0). Receipt: `notional-alias-mutation-receipt.json`. No additional production fix was needed for the EOF case.

Prior receipts under `docs/evidence/issue-1218/`: `mutation-receipts.json`, `numeric-mutation-receipts.json`, `sheet-selection-mutation-receipts.json`, `segment-mutation-receipts.json`, `completeness-mutation-receipt.json`, `cleanup-mutation-receipt.json`, `diagnostics-mutation-receipt.json`, `inference-mutation-receipt.json`, `header-precedence-mutation-receipt.json`, `segment-score-mutation-receipt.json`, `stop-marker-mutation-receipt.json`.

## Verified this follow-up

- [x] First ranked target (NISA) strengthened with an EOF regression case and targeted coverage verification.
- [x] Both deliberate truncation bugs fail the added case; restoring source passes.
- [x] Whole non-slow suite passes on supported Python 3.14; historical Python 3.12 results are explicitly labeled.
- [x] No production changes, thresholds, dependencies, or workflow edits in this follow-up.
- [ ] Hosted CI verifies the new commit.

Closes #1218
