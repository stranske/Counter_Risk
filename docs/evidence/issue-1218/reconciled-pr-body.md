## Summary

Expand regression coverage across issue #1218's ranked targets in escaped-defect, churn, then uncovered-mass order. Verified work on PR #1232 (`codex/issue-1218`) reduced uncovered target statements by **198** versus base `faad152`, exceeding the ~180-unit bundling goal. This closer pass reconciles evidence with the live PR head and reruns hosted Python CI after Gate run [41964641320](https://github.com/stranske/Counter_Risk/actions/runs/41964641320) skipped pytest jobs because path classification reported **0 changed files** (shallow checkout), not because the diff lacks Python.

The only production change fixes a real NISA header-alias bug: when a workbook places `Notional Change` or `Notional Change From Prior Month` before `Notional`, the generic `notional` substring used to capture the change column and the parser rejected the workbook as missing required headers. Match the specific `notional_change` aliases before the generic `notional` alias (three-line reorder plus comment). Two real-XLSX regression cases discriminate CH and totals; break-and-revert is recorded in `notional-alias-mutation-receipt.json`.

## Coverage

Line-only coverage (`branch = false` in repo config); no blended line+branch claim. Gate PR runs use `coverage: false`; numbers below are matched local whole non-slow suite runs on the repository-selected interpreter (`Counter_Risk/.venv/bin/python`, Python 3.12.2 on this host).

| Measure | Base `faad152` | PR head (current) |
|---|---:|---:|
| Statements | 10,911 / 12,216 | 11,109 / 12,216 |
| Percent | 89.3173% | **90.9381%** |
| Ranked-target delta | — | **198 fewer** uncovered statements |

| Target (issue order) | Missing before | Missing after | Before % | After % |
|---|---:|---:|---:|---:|
| parsers/nisa.py | 30 | 2 | 86.24% | 99.08% |
| compute/rollups.py | 16 | 0 | 94.86% | 100% |
| runner_launch.py | 14 | 0 | 92.75% | 100% |
| cli/mapping_diff_report.py | 12 | 1 | 87.76% | 98.98% |
| reports/mapping_diff.py | 12 | 0 | 87.88% | 100% |
| chat/providers/langchain_runtime.py | 9 | 2 | 96.17% | 99.15% |
| normalize.py | 5 | 0 | 95.54% | 100% |
| limits_config.py | 3 | 0 | 94.74% | 100% |
| chat/providers/base.py | 2 | 2 | 98.77% | 98.77% |
| ppt/pptx_postprocess.py | 54 | 0 | 66.46% | 100% |
| build/xlsm.py | 48 | 0 | 60.33% | 100% |

Seven defensive statements remain across ranked targets (documented unreachable via public contracts); this pass does not pad them.

**Historical vs current evidence:** Earlier commits on this branch (`3456860` … `8b786d70`) added the bulk tests and receipts under `docs/evidence/issue-1218/`. Keepalive commits reference PR #1220 in message text only; the live delivery PR is **#1232**. Alias follow-up at head `d92b97f0` adds zero additional covered statements over the prior candidate; it adds discrimination tests plus the alias fix.

## Validation (current head)

- **Local (2026-11-04, head `d92b97f0`):** `python -m pytest tests/ -m "not slow" -n 4 --dist load --cov=counter_risk --cov-report=term --cov-report=json:/tmp/issue-1218-current.json -q` → **2569 passed, 2 skipped**, 41.32s; coverage JSON **11,109 / 12,216 (90.9381%)**. One environment-specific failure (`test_validate_bundle_fails_when_gh_is_missing`) occurs when `gh` is on PATH locally; Gate pytest excludes integration/release markers and is the merge authority.
- **Break-and-revert (alias):** `notional-alias-mutation-receipt.json` — broken alias order **2 failed** (exit 1); restored fixed source **2 passed** (exit 0) for both parametrized labels.
- **Other mutations:** `mutation-receipts.json`, `numeric-mutation-receipts.json`, `sheet-selection-mutation-receipts.json`, `segment-mutation-receipts.json`, `completeness-mutation-receipt.json`, `cleanup-mutation-receipt.json`, `diagnostics-mutation-receipt.json`, `inference-mutation-receipt.json`, `header-precedence-mutation-receipt.json`, `segment-score-mutation-receipt.json`, `stop-marker-mutation-receipt.json` — each maps added scenarios to recorded red/green runs (no new parametrized cases without receipts in this pass).
- **Hosted Python CI:** Gate run 41964641320 skipped `Python CI` (`is-python-code=false`, 0 changed files). Remediation: label **`verify:full`** (or Gate `workflow_dispatch`) forces full classification and runs the standard reusable Python CI path without weakening gates. Record the successful run id and `headSha` here after the push retriggers Gate.

## Production bug rationale

Generic `notional` alias precedence swallowed `Notional Change*` headers when those columns appeared left of `Notional`, clearing `notional_change` from the resolved header map and failing validation. Reordering aliases fixes real workbook layouts without changing parsing semantics elsewhere.

## Verified contract tasks

1. [x] Ranked targets covered in issue order with discriminating tests.
2. [x] Break-and-revert recorded for new alias cases and prior mutation receipts for earlier additions.
3. [x] Minimal production fix only for the demonstrated alias defect.
4. [x] Low blast radius; no refactors, pins, thresholds, or workflow gate changes.
5. [x] Single PR **#1232** for this chunk (`Closes #1218`).

Closes #1218
