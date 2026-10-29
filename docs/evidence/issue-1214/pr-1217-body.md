## Summary

Add focused CLI and pipeline regression coverage. This round adds six cases that reject generated futures schemas with missing, reordered, or extra columns and reject missing or nonnumeric risk proxy values. Valid schemas remain accepted, error messages retain the offending schema/proxy context, and conversion errors preserve their cause. No production defect was found this round.

## Ranked selection and reconciliation

[Issue #1214](https://github.com/stranske/Counter_Risk/issues/1214) ranks CLI first (one escaped-defect signal, churn 1, 19 CI uncovered units), then pipeline (churn 15, 302 CI uncovered units). CLI is fully covered locally; this round continues pipeline. The reserved GUI runner is untouched.

Before new work, reviewed recent commits through `84f5ead` and audited all 144 then-collected PR-added cases against 63 mutation proofs. No cases were missing, duplicated, or uncollected. This verifies contract items 1–5 below. The live PR-body update was attempted before continuing but automatic approval review rejected it under approval policy `never`. This file contains the reconciled replacement body.

The final audit accounts for **150 cases across 66 executed mutation proofs**, with no gaps or duplicates. This remains the sole PR for this chunk.

## Coverage

The authoritative issue baseline remains **89.32% blended CI coverage**. The current local configuration measures lines only. These target-limited whole-suite reports cannot establish a blended CI reduction.

| Target | Existing tests before PR | Current PR | Missing lines |
|---|---:|---:|---:|
| `src/counter_risk/cli/__init__.py` | 218/237 (91.98%) | 237/237 (100.00%) | 19 → 0 |
| `src/counter_risk/pipeline/run.py` | 2334/2636 (88.54%) | 2552/2636 (96.81%) | 302 → 84 |

This round covers **5 additional statements**: 1818–1819 and 2290, 2293–2294. Pipeline missing lines fall from 89 to 84; coverage rises from 96.62% to 96.81%. The baseline contains all prior tests and excludes only this round's six cases. The PR's total local reduction is **237 lines**. The existing-tests baseline for the whole PR uses the final production source and excludes the three PR-added modules; earlier evidence preserves that measurement.

CLI has no local missing lines. Pipeline retains 84, including remaining invalid-data guards, alternative backends, and filesystem/Office failure paths. The approximately 180-unit blended CI reduction remains unverified; up to 180 comparable CI units are unconfirmed because the metrics differ. This is a partial delivery pending comparable CI coverage. Gate disables coverage, so a green Gate alone cannot establish that reduction.

## Verification and break-and-revert

- Whole non-slow suite: **2628 passed, 1 skipped, 87 deselected**, exit 0. Baseline: **2622 passed, 1 skipped, 87 deselected**, exit 0. Both use the same `pytest tests/ --cov=counter_risk.pipeline.run --cov=counter_risk.cli --cov-report=term-missing -m "not slow" -q -o addopts=` command with separate coverage files; no mutation overlapped either run.
- Required targeted check: `pytest tests/pipeline/test_run_coverage_round.py --cov=counter_risk.pipeline.run --cov-report=term-missing -m "not slow" -q -o addopts=`: **135 passed**, exit 0. Pipeline's standalone Cover column is **42%**; the whole-suite value is reported above.
- Disabled the futures schema guard: all three missing/reordered/extra-column cases **failed**, exit 1. Restored: all three **passed**, exit 0.
- Replaced rejection of a missing risk proxy with zero: the missing-value case **failed**, exit 1. Restored: **passed**, exit 0.
- Replaced rejection of conversion failures with zero: both invalid-text and invalid-type cases **failed**, exit 1. Restored: both **passed**, exit 0.
- Production SHA256 is identical before and after every mutation. `all-test-mutations.json` preserves all 66 proofs. This round's failures, restored passes, coverage tables, and formatter output are in `numeric-schema-guards-transcript.txt`; exact metrics and audit results are in `numeric-schema-guards-summary.json`. Earlier proofs remain in `break-and-revert.txt`.
- Formatted the changed Python file with `black --line-length 100`. The required repository-wide Black check and CI's check both passed across **398 files**. The ordinary check hit a sandbox process-pool permission failure; the single-worker attempt timed out. Both checks passed with `BLACK_NUM_WORKERS=1` and the previously documented temporary selector polling bound. The summary includes the helper source; formatter behavior was unchanged.
- CI's `ruff check --output-format github --extend-exclude .workflows-lib .` and `git diff --check` passed.
- Published-head CI for the six new cases remains pending publication; local success is not a CI claim.

## Production bug fixed earlier in this PR

Commit `0777d42` changes only the row-date predicate in `_extract_prior_populated_series_by_sheet`: a non-date footer previously replaced the last dated row, erasing the prior populated-series set used to detect dropped positions. The real-workbook regression fails with the old predicate and passes with `_coerce_historical_row_date`. No additional production change was made this round.

## Delivery blockers

- Earlier verified commits are published at starting head `84f5ead`.
- This round's workspace `git add` fails with `.git/index.lock: Read-only file system`. `/tmp/1217-numeric-schema.git` preserves the new commit; `/tmp/1217-numeric-schema.patch` is the handoff patch. The workspace branch cannot be advanced here.
- Git transport fails with `Could not resolve host: github.com`.
- Automatic approval review rejected the PR-body update, blocker comment, and `needs-human` label because **MCP tool call requires approval, but approval policy is never**. The live checkboxes could not be reconciled. A runner with publication access must publish the patch and apply this body.
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
