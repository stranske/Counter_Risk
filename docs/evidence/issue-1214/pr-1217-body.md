## Summary

Add focused CLI and pipeline regression tests. This round covers header-only and missing-cash CSV inputs under both warning and strict reconciliation policies. It verifies empty-source findings, empty override warnings, and preservation of existing totals and source files. No production change was needed this round.

## Ranked selection and task reconciliation

[Issue #1214](https://github.com/stranske/Counter_Risk/issues/1214) ranks CLI first (one escaped-defect signal, churn 1, 19 CI uncovered units), then pipeline (churn 15, 302 CI uncovered units). CLI is fully covered locally; this round continues with pipeline. The reserved GUI runner is untouched.

Reviewed recent commits through `f59df61`. The PR's three added test modules collect **140 cases**, matching **61 executed mutations** with no omissions, duplicates, or uncollected cases. Every mutated run exits 1 and every restored run exits 0. Contract items 1–5 below are verified and checked locally. Automatic approval review rejected the remote PR-body reconciliation, so the remote checkboxes remain stale.

## Coverage

The authoritative issue baseline remains **89.32% blended CI coverage**. The local configuration measures lines only; these target-limited whole-suite reports cannot establish a blended CI reduction.

| Target | Existing tests before PR | All PR tests | Missing lines |
|---|---:|---:|---:|
| `src/counter_risk/cli/__init__.py` | 218/237 (91.98%) | 237/237 (100.00%) | 19 → 0 |
| `src/counter_risk/pipeline/run.py` | 2334/2636 (88.54%) | 2542/2636 (96.43%) | 302 → 94 |

This round covers **4 additional statements**: 1428, 1501, 1504, 1511. Pipeline missing lines fall from 98 to 94. The PR's total local reduction is **227 lines**. The existing-tests baseline excludes the three PR-added modules and uses the final production source.

CLI has no local missing lines. Pipeline retains 94, including invalid-data guards, alternative output backends, and filesystem/Office failure paths; these remain test candidates. The roughly 180-unit blended CI reduction is unverified, with conservatively up to 180 CI units unconfirmed because the local line-only metric is not comparable. This remains a partial delivery pending publication and comparable Gate coverage. Exact summaries are in `empty-repo-cash-summary.json`.

## Verification and break-and-revert

- Whole non-slow suite: **2618 passed, 1 skipped, 87 deselected**, exit 0. Baseline: **2614 passed, 1 skipped, 87 deselected**. Command: `pytest tests/ --cov=counter_risk.pipeline.run --cov=counter_risk.cli --cov-report=term-missing -m "not slow" -q -o addopts=`.
- Required targeted check: `pytest tests/pipeline/test_run_coverage_round.py --cov=counter_risk.pipeline.run --cov-report=term-missing -m "not slow" -q -o addopts=`: **125 passed**, exit 0; standalone pipeline Cover column **41%**. The whole-suite pipeline result is **96.43%** above.
- Disabled the empty-source safeguard: **all four new cases failed**, exit 1. Restored it: **all four passed**, exit 0. Production SHA256 is identical before and after. `all-test-mutations.json` records all 61 mutations; `break-and-revert.txt` preserves failure/restoration output and the final coverage table.
- Formatted the changed Python file with `black --line-length 100`. Required repository-wide Black check and CI's check including `.venv` in the exclusion passed across **398 files**. The ordinary check timed out after 25s; both checks passed with `BLACK_NUM_WORKERS=1` and the temporary `EpollSelector.select` timeout bound documented in earlier rounds. Formatter behavior was unchanged.
- `ruff check --output-format github --extend-exclude .workflows-lib .` and `git diff --check` passed.
- Published-head [Gate 40853397510](https://github.com/stranske/Counter_Risk/actions/runs/40853397510) succeeded at `f59df61`. The four newest cases still require publication and CI.

## Production bug fixed earlier in this PR

Commit `0777d42` changes only the row-date predicate in `_extract_prior_populated_series_by_sheet`: a non-date footer previously replaced the last dated row, erasing the prior populated-series set used to detect dropped positions. The real-workbook regression fails with the old predicate and passes with `_coerce_historical_row_date`. No additional production defect was found. All other changes are focused tests and evidence in this one PR.

## Delivery blockers

- Workspace `git add` fails with `.git/index.lock: Read-only file system`. A Git directory under `/tmp` preserves a local commit of the verified source and evidence; `/tmp/1217-empty-repo-cash.patch` is the handoff patch. The workspace branch cannot be advanced here.
- Git transport fails with `Could not resolve host: github.com`, preventing push.
- Automatic approval review rejected PR-body reconciliation, the blocker comment, and the `needs-human` label because **MCP tool call requires approval, but approval policy is never**. The replacement body and checked contract items are preserved locally.
- PR #1217 is the sole PR for this chunk and remains open and ready for review (`isDraft=false`).

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
