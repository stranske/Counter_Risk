# Deliberate-break evidence: repo-cash NotionalChange sync (#1104 / #1107)

Linked issue: `stranske/Counter_Risk#1111` (D4 verification follow-up for merged PR #1107 / issue #1104).

## Mutation (temporary, not committed)

In `src/counter_risk/compute/rollups.py`, the line syncing `NotionalChange` to `notional_change`
after repo-cash application was removed:

```python
row["NotionalChange"] = row["notional_change"]
```

Production code on this branch keeps the merged fix; this file records the RED/GREEN transcript only.

## RED — sync removed, then

`pytest tests/compute/test_rollups.py::test_apply_repo_cash_syncs_notional_change_columns -q --no-cov`

```
FAILED tests/compute/test_rollups.py::test_apply_repo_cash_syncs_notional_change_columns
...
E       assert 1.0 == 5.5 ± 5.5e-06
============================== 1 failed in 14.56s ===============================
```

Representative failure: `notional_change` updated to 5.5 while `NotionalChange` stayed at the stale 1.0.

## GREEN — restored sync, same command

```
============================== 1 passed in 24.25s ===============================
```

## Verification command (this PR)

`pytest tests/compute/test_rollups.py::test_apply_repo_cash_syncs_notional_change_columns -q --no-cov`

Recorded on branch tip after sync with `origin/main` (2026-09-26).
