# Issue 1140: run directory safety

One bounded chunk of the coverage initiative. The starting measured value is below 90%; its rounded display is not a threshold decision. The initiative stays open.

## Selection and baseline

Source baseline: `262a811` (fetched main). Ranking uses the last 500 main source commits: fix/bug/repair/regression/correct subjects are a disclosed escaped-defect history proxy, then commit churn, then current uncovered mass. This is not a verified incident count.

| Source | Repair-history proxy | Churn | Uncovered statements |
|---|---:|---:|---:|
| `src/counter_risk/pipeline/run.py` | 19 | 110 | 327 |
| `src/counter_risk/writers/historical_update.py` | 8 | 39 | 36 |
| `src/counter_risk/build/release.py` | 6 | 23 | 17 |
| `src/counter_risk/compute/futures_delta.py` | 6 | 19 | 9 |
| `src/counter_risk/compute/rollups.py` | 5 | 15 | 16 |

Command on baseline and candidate (same interpreter, marker and coverage scope):

```sh
python -m pytest -q -n 4 -m 'not release and not slow' --cov=counter_risk --cov-report=json:coverage.json
```

Baseline: **2,194 passed, 1 skipped**; 48 release/slow nodes outside this local scope. 10,812 / 12,035 production statements covered (**89.837973%**, display rounds to 90). Selected `pipeline/run.py`: 2,181 / 2,508 (**86.961722%**), 327 missing. Directory guard lines 842, 845, 846, 854 and 874 were uncovered. An earlier serial run was interrupted for the four-worker run; only the completed parallel run supplies this baseline.

## Reproduced defect and repair

A deterministic filesystem interleaving creates the date directory, with another run's manifest, after the existence check but before this run's `mkdir`. Original source raises `FileExistsError`: new suite **1 failed, 6 passed**. Catch only that collision and advance to the next suffix. Explicit output paths retain fail-closed behavior; other filesystem errors still propagate. The regression checks the other manifest is unchanged and the returned suffix directory is empty.

## Actual per-test mutation controls

Each row ran its exact node with `python -m pytest tests/test_pipeline_run_dir_safety.py::<node> -q`. Each mutation exited 1 and the listed node appeared in pytest's FAILED summary. Source bytes were restored after every control and in `finally`; the final source hash is recorded below. Controls protect existing safety behavior as well as the new fix: six tests passing on historical source is expected, not proof of a hollow gate.

| Mutation | Named node | Actual RED |
|---|---|---|
| `file-guard` | `test_explicit_file_is_rejected_without_modifying_it` | 1 failed, exit 1 |
| `inspection-cause` | `test_unreadable_output_directory_retains_filesystem_cause` | 1 failed, exit 1 |
| `empty-directory` | `test_existing_empty_output_directory_is_reused` | 1 failed, exit 1 |
| `owned-folders` | `test_automatic_run_preserves_owned_folders_and_uses_next_suffix` | 1 failed, exit 1 |
| `atomic-claim` | `test_concurrent_run_directory_claim_advances_without_reusing_other_run` | 1 failed, exit 1 |
| `exhaustion` | `test_exhausted_run_names_fail_without_reusing_any_directory` | 1 failed, exit 1 |
| `noncollision-error` | `test_automatic_run_does_not_swallow_noncollision_filesystem_error` | 1 failed, exit 1 |

Mutations respectively bypassed the explicit file guard, dropped exception wrapping, broke empty-directory reuse, reused an owned folder, removed atomic collision recovery, returned a folder after name exhaustion, and swallowed noncollision errors. The complete console transcript is [issue-1140-run-directory-transcripts.txt](issue-1140-run-directory-transcripts.txt); machine-local path prefixes are redacted and trailing whitespace normalized, while test names, failures, source lines and outcomes are preserved.

Restoration command:

```sh
python -m pytest tests/test_pipeline_run_dir_safety.py tests/test_pipeline_run_dir.py -q
# 12 passed in 0.42s
```

Byte-identical restored `src/counter_risk/pipeline/run.py` SHA256: `10038a2a20f1a6167d0e6992bc212e89546169d0a7e524350a4b2574b983723b`.

## Candidate validation

Candidate: **2,201 passed, 1 skipped** in299.77s, with the same48 release/slow deselections. Total 10,820 / 12,038 (**89.882040%**), +8 covered statements. Selected module 2,189 / 2,511 (**87.176424%**), +8 covered statements. The exact total remains below90%; the broad initiative stays open. Black/Ruff passed on both changed Python files; mypy reports no issues in the changed production module. No production workflow, floor, coverage exclusion or marker configuration changed. Local tests do not establish hosted/Office/native integration or current-head GitHub acceptance. Keepalive owns new-head CI/review; closer owns full chunk acceptance and verifier disposition.
