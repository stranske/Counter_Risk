## Summary

PR **#1232** merged to `main` as **`ce163635`** (2026-11-05). This closer repair does not revert or redo that delivery; it reconciles the final test diff against mutation receipts, records hosted supported-version CI on the merge commit, and documents target-ranking evidence.

## Test diff reconciliation (final state on main)

Reviewed full diffs of `tests/compute/test_rollups.py`, `tests/test_nisa_all_programs_parser.py`, and `tests/test_python_floor.py` from issue base `faad152` through merge commit `ce163635`.

| Added / strengthened tests | Mutation / discrimination evidence |
|---|---|
| `test_repo_cash_accumulates_aliases_into_one_counterparty` (2 parametrized) | `rollups-alias-mutation-receipts.json` — alias lookup bypass, row-zero falsy index, signed cash; locally re-run 2026-11-05: each break **2 failed**, restore **2 passed** |
| Rollups coverage helpers (`test_compute_totals_*`, `test_repo_cash_*`, `test_notional_breakdown_*`, `test_top_*`) | `mutation-receipts.json` — one deliberate break per test name, red then green |
| `test_parser_reads_workbook_without_dimension_record` — **eof** parametrization asserts `Final Bank` totals at EOF | `eof-mutation-receipts.json` — totals upper bound and cached max_row − 1; locally re-run: **1 failed (eof), 1 passed** per scenario, restore **2 passed** |
| NISA sheet / header / segment / numeric / completeness / cleanup / stop-marker / notional-order cases | Matching `docs/evidence/issue-1218/*mutation*.json` receipts (committed with PR #1232) |
| `test_python_floor.py` tool-target parametrization | No production mutation: negative `tool` dict fixtures must fail `_assert_tool_targets`; positive fixtures pass. Strengthens config guards only. |

**EOF inclusion:** `with_stop_marker=False` adds row 26 (`Final Bank`, notional 321) and asserts totals include that row after stripping `<dimension/>`.

**Alias output assertions:** `test_repo_cash_accumulates_aliases_into_one_counterparty` asserts single Citibank row, signed `Cash`, and both notional / notional_change alias pairs updated.

## Target ranking evidence

Historical issue order and before/after missing-line lists live in `coverage-summary.json` → `targets_in_issue_order` (Python **3.12.2**, line-only, base `faad152`). The original autopilot ranking script transcript is **not** archived; ordering is **reconstructed** from that JSON field and matches the issue’s ranked module list. Historical whole-repo gain: **198 fewer missing statements** (10,911 → 11,109 of 12,216 statements).

## Local verification (closer repair)

Interpreter: repository `.venv/bin/python` (Python **3.12.2**).

```
python -m pytest tests/ -m "not slow" -n 4 --dist load --cov=counter_risk --cov-report=term -q
```

Result: **3054 passed, 2 skipped, 1 failed** in 48.35s; TOTAL **96%** (510 missing lines). The single failure is `test_validate_bundle_fails_when_gh_is_missing` because `gh` is on this machine’s PATH (message lacks expected `'gh'` substring). Not part of #1218 additions; hosted CI uses a controlled environment.

Focused three-file run: **123 passed** in 5.26s.

## Hosted supported-version CI (merge commit with all final tests)

Gate run [**41991482374**](https://github.com/stranske/Counter_Risk/actions/runs/41991482374) on **`ce163635`**: Python **3.13** and **3.14** jobs **success**; ruff, black, mypy **success**. This verifies the merged PR #1232 test set on supported versions.

## Branch reconciliation

`closer-r1/issue-1218` had no commits ahead of `origin/main` before this repair; nothing kept/discarded from other local closer branches.

Refs #1218
