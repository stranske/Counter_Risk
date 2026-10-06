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

## Separate-process acceptance verification

The follow-up regression `test_separate_processes_claim_distinct_run_directories` starts two independent Python processes using the `spawn` context. A barrier makes both processes observe the same candidate as absent before either attempts directory creation. Both must exit successfully, return the base name and its `_1` suffix, and retain their own manifest contents. The test covers both the as-of-date name and the name with an explicit run date. Worker timeouts and cleanup keep a broken collision handler from hanging the suite.

Removing only the `FileExistsError` recovery makes **both parameter cases fail**, with a child process reporting `FileExistsError` and exiting 1. Production source was restored byte-for-byte in `finally`, retaining SHA256 `10038a2a20f1a6167d0e6992bc212e89546169d0a7e524350a4b2574b983723b`. The complete failure output is in [issue-1140-process-claims-transcript.txt](issue-1140-process-claims-transcript.txt).

Validation after restoration, on Python 3.14.7:

```sh
python -m pytest tests/test_pipeline_run_dir_safety.py tests/test_pipeline_run_dir.py \
  -q -m 'not slow' --cov=counter_risk.pipeline.run --cov-report=term-missing \
  --cov-report=json:/tmp/run-directory-claims-coverage.json
# 14 passed in 2.39s
```

The targeted coverage table reports **588 / 2,511 statements (23%)** for the entire `pipeline/run.py` module. Within `_create_run_directory`'s AST line span, the coverage JSON records **28 / 28 executable lines covered (100%)**, with no missing lines. This focused run does not rerun or replace the broader baseline/candidate comparison above; no new repository-wide coverage gain is claimed. These are line-coverage results, not branch-coverage measurements.

`ruff check tests/test_pipeline_run_dir_safety.py` passed. The repository-wide formatting gate also passed, reporting **368 files would be left unchanged**:

```sh
BLACK_CACHE_DIR=/tmp/counter-risk-black-cache \
  black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

The sandbox denied Black's default process startup, and its alternative worker executors stalled. A temporary launcher checked every selected file serially with the installed Black formatter and populated the writable cache; the standard CLI command above then passed. No formatter configuration or file-selection exclusions changed.

Local acceptance checklist, completed after the restored-source validation:

* [x] **Bug Fixes**
  * [x] Run directory creation now moves on to the next available name if another process claims a candidate directory at the same time.
* [x] **Tests**
  * [x] Added coverage for existing files and directories, concurrent directory creation, exhausted run names, and filesystem errors.
* [x] **Documentation**
  * [x] Added test results and coverage notes for run-directory safety. Hosted, Office, and native integration, as well as current-head GitHub acceptance, are not established.

The new process tests ran locally on Linux. Hosted, Office, and native integration remain unverified. GitHub's API was unreachable during this follow-up, so the live PR checkboxes, readiness, and current-head GitHub acceptance could not be verified or updated.

## Boundary regressions and renewed measurement (2026-10-06)

This keepalive started from `d62fd77`. Before edits, the exact full measurement command
above passed: **2,203 passed, 1 skipped in 366.20s** on Python 3.14.7. Production
coverage was **10,820 / 12,038 (89.88204020601428%)**, with **1,218 missing lines**
and 84 excluded lines. This remains below the 90% stopping threshold despite the
rounded display. The broader initiative remains open.

The renewed ranking uses the last 500 production-source commits reachable from
the starting HEAD. The repair-history proxy matches whole words
`fix|bug|repair|regression|correct` in commit subjects, case-insensitively; it does
not count words such as "fixture" and is still not an incident count. Sort keys
are repair-history proxy, churn, then uncovered statements, all descending.

| Source | Repair-history proxy | Churn | Uncovered statements |
|---|---:|---:|---:|
| `src/counter_risk/pipeline/run.py` | 20 | 111 | 322 |
| `src/counter_risk/writers/historical_update.py` | 8 | 39 | 36 |
| `src/counter_risk/build/release.py` | 6 | 23 | 17 |
| `src/counter_risk/compute/futures_delta.py` | 6 | 19 | 9 |
| `src/counter_risk/compute/rollups.py` | 5 | 15 | 16 |

The selected module remains `pipeline/run.py`, with **2,189 / 2,511 statements
covered (87.17642373556352%)**. The allocator itself already has **28 / 28
executable lines covered**, so this follow-up strengthens missing safety cases
within the existing logical chunk. It does not claim new line coverage or a new
production defect. No production repair was needed for these cases.

The added regressions verify that an explicit-path collision raises without
reusing another run's directory, repeated automatic claims by files advance to
the next free directory for both naming modes, and suffix `_9999` can still be
claimed before exhaustion. Every new case ran its own real mutation and
restoration with `python -m pytest tests/test_pipeline_run_dir_safety.py::<node>
-q -m 'not slow'`:

| Named test node | Deliberate source mutation | Actual RED | Restored GREEN |
|---|---|---|---|
| `test_explicit_output_claim_collision_preserves_other_run_and_raises` | Set explicit-path `mkdir` to `exist_ok=True` | `DID NOT RAISE FileExistsError`; 1 failed, exit 1 | 1 passed, exit 0 |
| `test_repeated_file_claim_collisions_advance_to_next_free_run_directory[as-of]` | Return the contested path from the collision handler | Path equality assertion fails; 1 failed, exit 1 | 1 passed, exit 0 |
| `test_repeated_file_claim_collisions_advance_to_next_free_run_directory[run-date]` | Return the contested path from the collision handler | Path equality assertion fails; 1 failed, exit 1 | 1 passed, exit 0 |
| `test_last_available_run_suffix_is_claimed_before_exhaustion` | Shorten suffix range from `range(1, 10_000)` to `range(1, 9_999)` | `RuntimeError: Unable to create unique run directory`; 1 failed, exit 1 | 1 passed, exit 0 |

The [complete boundary mutation transcript](issue-1140-boundary-transcript.txt)
contains each actual failure, individual restored pass, and the final targeted
coverage run. Production source was restored byte-for-byte after every mutation
and in `finally`, with SHA256
`10038a2a20f1a6167d0e6992bc212e89546169d0a7e524350a4b2574b983723b`.
The restored focused suite passed **18 tests in 1.63s**. Its module table shows
**588 / 2,511 (23%)**; the allocator's AST span remains **28 / 28 (100%)**, with
zero missing lines. Full-module and per-function measurements are distinct.

Black formatted the changed test file and Ruff passed. The required whole-repo
Black CLI check passed, reporting **368 files would be left unchanged**, using
the same writable cache and serial cache-population workaround documented above.
The initial single-worker executor stalled and was interrupted; the serial
formatter checked the CLI-selected files, and the subsequent standard command
exited 0:

```sh
BLACK_CACHE_DIR=/tmp/counter-risk-black-cache \
  black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

### Same-scope comparison for this follow-up

Both full runs used `--cov=counter_risk` and `-m 'not release and not slow'`,
four workers, the same interpreter and coverage configuration. The production
source bytes were identical. The baseline selected 2,204 nodes and the candidate
selected 2,208; all four added nodes are unmarked. Collection confirms the same
**48 release/slow deselections**. Local coverage is line-only and excludes those
tests; it does not establish Office, native, hosted or current-head GitHub
integration behavior.

| Measurement | Starting HEAD | Candidate |
|---|---:|---:|
| Passed / skipped | 2,203 / 1 | 2,207 / 1 |
| Full-suite duration | 366.20s | 343.60s |
| Production covered / total statements | 10,820 / 12,038 | 10,820 / 12,038 |
| Production missing lines | 1,218 | 1,218 |
| Exact production coverage | 89.88204020601428% | 89.88204020601428% |
| Selected module covered / total statements | 2,189 / 2,511 | 2,189 / 2,511 |
| Selected module missing lines | 322 | 322 |
| Allocator covered / total executable lines | 28 / 28 | 28 / 28 |

The coverage JSON's complete per-file results, including missing-line arrays,
match exactly. The actual change for this follow-up is **zero covered lines and
zero percentage points**. The earlier main-to-initial-fix improvement remains
the +8 covered statements recorded above. The
[full coverage transcript](issue-1140-boundary-coverage-transcript.txt) preserves
both complete console runs, collection counts, ranking, and every production
file's missing-line list and statistics.

Verified local task checklist for the previously unchecked tasks:

- [x] Measure `src/counter_risk` with the required full command and rank production gaps.
- [x] Add focused regressions for the selected production symbol; no further reproduced defect required repair.
- [x] Actually mutate each newly tested behavior, restore exact source bytes, and record RED/GREEN results here.
- [x] Both focused run-directory test files pass; each added test case has an actual named mutation failure and restoration.
- [x] Baseline/candidate full local runs have identical package scope and marker selection, with counts, uncovered lines, ranking, limitations and actual change captured.
- [x] Starting coverage is below 90%; keep this test-only follow-up in the existing low-risk run-directory chunk and leave the broader initiative open.

GitHub's API remained unreachable during this run. This checklist records local
verification; it does not claim that live PR checkboxes, readiness or current-head
GitHub acceptance were updated or verified.

The final focused rerun passed **18 tests in 1.89s** with no failures, and
`git diff --check` passed. The requested commit could not be made: staging failed
with `fatal: Unable to create '<repo>/.git/index.lock': Read-only file system`.
The tested Python changes and evidence remain in the working tree for the
automation runner or a maintainer to commit in a writable checkout.
Attempts to post the blocker comment and add `needs-human` also failed because
`api.github.com` was unreachable; neither remote action was completed.


## Errors after an automatic claim collision (2026-10-06)

Starting HEAD: `e56ecf9`. The first measurement/ranking task was already
verified by the preceding completed runs, so this follow-up uses the archived
candidate (**2,207 passed, 1 skipped**, 89.88204020601428%) as its baseline
rather than repeating it. The production tree is unchanged from `d62fd77`:
`610589c4a8f563caed2dca24a6a2785830c6f563`. This is below the 90% stopping threshold.
The refreshed 500-production-commit ranking is unchanged: `pipeline/run.py`
(repair-history proxy 20, churn 111, 322 missing), `historical_update.py`
(8, 39, 36), `build/release.py` (6, 23, 17), `futures_delta.py` (6, 19, 9),
then `rollups.py` (5, 15, 16). The proxy remains a whole-word commit-subject
match, not a verified incident count.

The previous noncollision-error test fails while creating the run root, before
the candidate's collision handler. The new parametrized regression creates the
parent first, forces another run to claim the base name, then raises an actual
`EACCES` or `ENOSPC` error while claiming suffix `_1`. It requires propagation
of that same exception object, exactly two claim attempts, and preservation of
the other run's sole manifest. Both cases pass on current production code;
no new defect or production repair is claimed.

Each case ran its own mutation, widening `except FileExistsError` to
`except OSError`. Each actual RED swallowed the error, exhausted the names,
and raised `RuntimeError: Unable to create unique run directory` instead.

| Exact node in `tests/test_pipeline_run_dir_safety.py` | Actual mutation RED | Exact-source restored GREEN |
|---|---|---|
| `test_automatic_claim_error_after_collision_propagates_without_reusing_other_run[permission]` | 1 failed, exit 1 | 1 passed, exit 0 |
| `test_automatic_claim_error_after_collision_propagates_without_reusing_other_run[disk-full]` | 1 failed, exit 1 | 1 passed, exit 0 |

The [complete mutation transcript](issue-1140-claim-errors-transcript.txt)
records each named failure, individual restoration, and the restored focused
suite: **20 passed in 2.55s**. Source bytes were restored after every mutation
and in `finally`; SHA256 remains `10038a2a20f1a6167d0e6992bc212e89546169d0a7e524350a4b2574b983723b`.
Targeted `--cov=counter_risk.pipeline.run -m 'not slow'` reports **588 / 2,511
statements (23%)** for the full module and **28 / 28 executable lines (100%)**
within the allocator's AST span, with no missing lines.

The fresh full candidate used the exact package scope and marker selection
shown above: **2,209 passed, 1 skipped in 640.63s**, **2,210 selected**,
and the same **48 release/slow deselections**. Both baseline and candidate
cover **10,820 / 12,038 production statements (89.88204020601428%)**, with
**1,218 missing** and **84 excluded** lines. The selected module remains
**2,189 / 2,511 (87.17642373556352%)**, with **322 missing** lines. All
**106 per-file summaries and missing-line lists** match the archived
baseline exactly: the actual change is **zero covered lines and zero percentage
points**. These regressions strengthen behavior coverage within the same low-risk
chunk; the broader initiative remains open. The
[full candidate coverage transcript](issue-1140-claim-errors-coverage-transcript.txt)
records the baseline provenance, console output, collection, refreshed ranking,
comparison, and every production file's missing lines. These are local line
coverage measurements; release/slow, Office, native and hosted integration,
and current-head GitHub acceptance remain outside their scope.

Black formatted the changed test file, Ruff passed, and the required whole-repo
Black CLI check passed with **368 files unchanged**. As in the previous run,
the executor stalled; a temporary serial launcher checked the same CLI-selected
files using Black's normal formatter and populated the writable cache, then
the standard `black --check --line-length 100 --exclude
'(\.workflows-lib|node_modules)' .` command passed. No formatting configuration,
coverage floor, exclusion, marker, or workflow was changed.

Local staging remains blocked by the checkout's read-only `.git` directory.
The GitHub connector's read APIs work, but `create_tree` was rejected with
`MCP tool call requires approval, but approval policy is never`. The required
`needs-human` label and blocker-comment attempts were rejected with the same
message. No tree, commit, branch update, live checklist update, label, or comment
was created. The tested Python changes and evidence remain in the workspace for
a writable checkout or runner authorized for GitHub writes. PR #1142 was verified
open with `draft=false`; current-head GitHub acceptance remains unverified.

Locally verified follow-up tasks:

- [x] Required package measurement and production gap ranking are recorded.
- [x] Both newly added regression cases fail real mutations and pass after exact-source restoration.
- [x] Both focused test files pass, and the full same-scope candidate passes with the baseline comparison recorded.
- [ ] Commit and deliver the tested source/evidence changes, then update live task checkboxes; blocked by the write restrictions above.


## Saved-artifact latency boundary reconciliation (2026-10-06)

The subsequent saved-artifact chunk supplements this completed directory-safety
work. Fresh directory validation passes all 20 tests. The three newly tested
latency nodes each fail their actual mutation and pass after exact restoration:

| `tests/pipeline/test_fleet_artifact_fallbacks.py::test_fleet_artifact_uses_first_valid_nonnegative_latency[primary-preferred]` | `if parsed >= 0 and (key != "LANGSMITH_TRACE_LATENCY_MS" or parsed == 0):` | 1 failed / exit 1 | 1 passed / exit 0 |
| `tests/pipeline/test_fleet_artifact_fallbacks.py::test_fleet_artifact_uses_first_valid_nonnegative_latency[fractional-to-secondary]` | `parsed = int(float(value))` | 1 failed / exit 1 | 1 passed / exit 0 |
| `tests/pipeline/test_fleet_artifact_fallbacks.py::test_fleet_artifact_uses_first_valid_nonnegative_latency[absent-to-tertiary]` | `if raw is None: return None` | 1 failed / exit 1 | 1 passed / exit 0 |
| `tests/pipeline/test_fleet_artifact_fallbacks.py::test_fleet_artifact_uses_pipeline_error_after_blank_trace_category` | `return "unknown-category"` | 1 failed / exit 1 | 1 passed / exit 0 |
| `tests/pipeline/test_fleet_artifact_fallbacks.py::test_fleet_artifact_omits_external_report_paths` | `"report_artifact_count": len(report_refs) or 1,` | 1 failed / exit 1 | 1 passed / exit 0 |

Fresh identical-package full measurements: baseline **2216 passed, 1 skipped in 989.51s (0:16:29)**,
candidate **2219 passed, 1 skipped in 700.37s (0:11:40)**; `counter_risk`, four workers,
`not release and not slow`, 48 deselections each. Coverage is
**10825/12038 (89.923575344742%)**
to **10825/12038 (89.923575344742%)**,
with **+0 covered statements**. The refreshed repair-history/churn/missing-line
ranking, all per-file missing lines, exact restoration hashes, full console
outputs, and scope limits are in
[the saved-artifact evidence](issue-1140-fleet-artifact-fallbacks.md),
[its JSON](issue-1140-fleet-artifact-fallbacks.json), and
[its transcript](issue-1140-fleet-artifact-fallbacks-transcript.txt).
The broader initiative stays open below 90 percent. Python 3.12's missing pytest
and rejected GitHub writes leave those specific acceptance/delivery actions open.
