## Summary

Add focused CLI and pipeline regression tests, with one previously recorded production fix for historical row-date detection. This round adds four cases for empty totals and incomplete prior-month change data. It checks that later variants still produce metrics, that valid exposures remain available, and that missing changes are not presented as zero changes. No additional production change was needed.

## Ranked selection and task reconciliation

[Issue #1214](https://github.com/stranske/Counter_Risk/issues/1214) ranks CLI first (one escaped-defect signal, churn 1, 19 CI uncovered units), then pipeline (churn 15, 302 CI uncovered units). CLI is fully covered locally; this round continues with pipeline. The reserved GUI runner is untouched.

The PR's three added test modules collect **144 cases**. The evidence registry contains **63 executed mutation proofs**, with no missing, duplicate, or uncollected cases. This round adds two mutation proofs covering all four new cases: every broken case failed and every restored case passed. Contract items 1–5 below are verified locally. This remains the sole PR for the chunk.

## Coverage

The authoritative issue baseline remains **89.32% blended CI coverage**. The current local configuration measures lines only; these target-limited whole-suite reports cannot establish a blended CI reduction.

| Target | Existing tests before PR | All PR tests | Missing lines |
|---|---:|---:|---:|
| `src/counter_risk/cli/__init__.py` | 218/237 (91.98%) | 237/237 (100.00%) | 19 → 0 |
| `src/counter_risk/pipeline/run.py` | 2334/2636 (88.54%) | 2547/2636 (96.62%) | 302 → 89 |

This round covers **5 additional statements**: 1924–1926, 1955–1956. Pipeline missing lines fall from 94 to 89; this round's whole-suite baseline excludes only its four new cases. The PR's total local reduction is **232 lines**. The existing-tests baseline for the full PR excludes the three PR-added modules and uses the final production source; it is preserved in earlier evidence.

CLI has no local missing lines. Pipeline retains 89, including invalid-data guards, alternative output backends, and filesystem/Office failure paths; these remain test candidates. The roughly 180-unit blended CI reduction remains unverified, with up to 180 comparable CI units unconfirmed because the metrics differ. This is a partial delivery pending publication and comparable CI coverage. Gate currently disables coverage, so its success alone cannot establish that reduction.

## Verification and break-and-revert

- Clean whole non-slow suite: **2622 passed, 1 skipped, 87 deselected**, exit 0. Baseline excluding the four new cases: **2618 passed, 1 skipped, 91 deselected**, exit 0. Both run `pytest tests/ --cov=counter_risk.pipeline.run --cov=counter_risk.cli --cov-report=term-missing -m "not slow" -q -o addopts=` with separate coverage files.
- Required targeted check: `pytest tests/pipeline/test_run_coverage_round.py --cov=counter_risk.pipeline.run --cov-report=term-missing -m "not slow" -q -o addopts=`: **129 passed**, exit 0. The pipeline Cover column is **41%** standalone; the whole-suite result is **96.62%** above.
- Changed the empty-totals branch to return before processing later variants: **both new cases failed**, exit 1. Restored it: **both passed**, exit 0.
- Disabled the incomplete-change-column safeguard: **both new cases failed** because absent changes became zero values, exit 1. Restored it: **both passed**, exit 0. Production SHA256 is identical before and after both mutations.
- `all-test-mutations.json` records all 63 proofs. `break-and-revert.txt` preserves failure/restoration output and final coverage tables. Exact clean coverage summaries and the case audit are in `metrics-guards-summary.json`. An initial pair of overlapping runs shared a coverage file; their coverage reports were discarded and replaced by the isolated clean runs above.
- Formatted the changed Python file with `black --line-length 100`. Both the required repository-wide Black check and CI's check including `.venv` in the exclusion passed across **398 files**. The ordinary check timed out after 30 seconds; both checks passed with `BLACK_NUM_WORKERS=1` and the temporary `EpollSelector.select` timeout bound documented in earlier rounds. Formatter behavior was unchanged.
- CI's `ruff check --output-format github --extend-exclude .workflows-lib .` and `git diff --check` passed.
- The new cases have passed locally; published-head CI remains pending publication.

## Production bug fixed earlier in this PR

Commit `0777d42` changes only the row-date predicate in `_extract_prior_populated_series_by_sheet`: a non-date footer previously replaced the last dated row, erasing the prior populated-series set used to detect dropped positions. The real-workbook regression fails with the old predicate and passes with `_coerce_historical_row_date`. No additional production defect was found. All other changes are focused tests and evidence in this one PR.

## Delivery blockers

- Workspace `git add` fails with `.git/index.lock: Read-only file system`. `/tmp/1217-metrics.git` preserves a commit of the verified source and evidence. `/tmp/1217-metrics.patch` is the handoff patch; the workspace branch cannot be advanced here.
- Git transport fails with `Could not resolve host: github.com`, preventing push.
- Automatic approval review rejected creating a GitHub tree for the updated test file because **MCP tool call requires approval, but approval policy is never**. Reconciliation outcomes are recorded in `metrics-guards-summary.json`.
- PR #1217 is open and ready for review (`isDraft=false`).

Closes #1214

<!-- pr-preamble:start -->
<!-- meta:issue:1214 -->
> **Source:** Issue #1214

Closes #1214

<!-- pr-preamble:end -->

<!-- auto-status-summary:start -->
## Automated Status Summary

#### Scope

Counter_Risk reads 89.32% blended line+branch in CI; reaching 90% needs about 145 more covered statements+branches. The target order below is the Orchestrator's own ranking (escaped defects, then churn, then uncovered mass -- unchanged). Only the bundling is new: earlier rounds spent a whole PR on files with a handful of uncovered statements, so one PR now covers the next ranked targets until it has covered about 180 units.

#### Tasks

- [x] "Uncovered units" here come from the repository's whole CI run (every test file together). One test module's own suite can already cover more than CI's count shows for that module, and CI's figure is the one this PR is judged on: if your baseline differs, say so in the PR body and use CI's number.
- [x] Before you push, run the repository's own formatter and linter on every file you add or change, with the flags its CI `lint-format` and `lint-ruff` jobs use: one unformatted file fails a required check, and waiting for the autofix bot to repair it afterwards has not worked on lane PRs.
- [ ] Deliver what you verified. If you cannot reach the goal for ANY reason (a broken local environment, a target you could not finish, the time you had), still open the pull request with the verified work you have, say in its body how far short it is and why, and never leave verified commits or edits unpushed or uncommitted: a partial pull request that merges is worth more than a complete one that never opens, and a worktree left holding work blocks this issue's next dispatch.

#### Acceptance criteria

- [ ] `pytest` passes in CI with the new tests, and each new test fails when the code it covers is deliberately broken (the PR body shows the break-and-revert run).
- [x] The PR's Gate coverage shows the targets' uncovered statements+branches down by about 180 or more, or the PR body states how far short it is and why and explains each target that could not be meaningfully covered (a partial PR meets this criterion; no PR does not).
- [x] Production code changes only where a test found a real bug, each one explained in the PR body.

- [x] Same contract as every round in this initiative:
1. [x] Pick the next target by the repo's own coverage-gap ranking (escaped-defect priority, then
   churn, then uncovered mass), not by file size.
2. [x] Every new test must FAIL when the code it covers is deliberately broken and PASS when
   reverted -- run that break-and-revert for real and report it, don't assert it.
3. [x] Real bugs found while writing tests get fixed with a minimal, targeted diff in the same PR,
   not worked around. Watch for the negative-cache pattern (cache.get(key) is None used as a 'not yet cached' check, which can't tell 'never queried' from 'queried and got nothing') -- it has recurred independently four separate times fleet-wide already.
4. [x] Low blast radius only -- test-only or tightly-scoped fixes, no refactors.
5. [x] One PR per logical chunk of work.

- [x] The goal is to improve the code, not a metric. If you measure this repo at or above 90% before
- [x] starting, say so in a comment on this issue and close it without opening a PR -- do not
- [x] manufacture a fix just because a round was requested.

<!-- auto-status-summary:end -->
