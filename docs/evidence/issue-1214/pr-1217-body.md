## Summary

Add focused CLI and pipeline regression coverage. This round adds four Windows chart-replacement cases covering both linked and static modes, successful rebuilding, and ordinary rebuild failures. They check one-based slide exports, fallback-image forwarding, Office cleanup before rebuilding, result status, and error details. No production defect was found this round.

## Ranked selection and reconciliation

[Issue #1214](https://github.com/stranske/Counter_Risk/issues/1214) ranks CLI first (one escaped-defect signal, churn 1, 19 CI uncovered units), then pipeline (churn 15, 302 CI uncovered units). CLI is fully covered locally; this round continues pipeline. The reserved GUI runner is untouched.

At starting head `7215c74`, audited all 150 collected PR-added cases against 66 executed mutation proofs. No cases were missing, duplicated, or uncollected. The issue ranking, production diff, and single open PR support all five contract items below. The final audit accounts for **154 cases across 68 mutation proofs**, with no gaps or duplicates. This remains the sole PR for this chunk.

## Coverage

The authoritative issue baseline remains **89.32% blended CI coverage**. The current local configuration measures lines only. These target-limited whole-suite reports cannot establish a blended CI reduction.

| Target | Existing tests before PR | Verified current tree | Missing lines |
|---|---:|---:|---:|
| `src/counter_risk/cli/__init__.py` | 218/237 (91.98%) | 237/237 (100.00%) | 19 → 0 |
| `src/counter_risk/pipeline/run.py` | 2334/2636 (88.54%) | 2557/2636 (97.00%) | 302 → 79 |

This round covers **5 additional statements**: 3148, 3176–3177, and 3185–3186. Pipeline missing lines fall from 84 to 79; coverage rises from 96.81% to 97.00%. The PR's total local reduction is **242 lines**. The before-round baseline contains all prior tests; the existing-tests baseline for the whole PR uses the final production source and excludes the three PR-added modules, as preserved in earlier evidence.

CLI has no local missing lines. Pipeline retains 79, including remaining invalid-data guards, alternative backends, and filesystem/Office failure paths. The approximately 180-unit blended CI reduction remains unverified; all 180 comparable CI units remain unconfirmed because the metrics differ. This is a partial delivery pending comparable CI coverage. Gate disables coverage, so a green Gate alone cannot establish that reduction. No exclusions, thresholds, or unrelated production code were changed.

## Verification and break-and-revert

- Whole non-slow suite: **2632 passed, 1 skipped, 87 deselected**, exit 0. Before-round baseline: **2628 passed, 1 skipped, 87 deselected**, exit 0. Both use `pytest tests/ --cov=counter_risk.pipeline.run --cov=counter_risk.cli --cov-report=term-missing -m "not slow" -q -o addopts=` with isolated coverage files. Neither overlapped a source mutation or test edit.
- Required targeted check: `pytest tests/pipeline/test_run_coverage_round.py --cov=counter_risk.pipeline.run --cov-report=term-missing -m "not slow" -q -o addopts=`: **139 passed**, exit 0. Pipeline's standalone Cover column is **44%**; whole-suite coverage is reported above.
- Dropped collected fallback paths before rebuilding: both linked/static success cases **failed**, exit 1. Restored: both **passed**, exit 0.
- Removed the original exception detail from the rebuild-failure warning: both linked/static failure cases **failed**, exit 1. Restored: both **passed**, exit 0.
- Production SHA256 is identical before and after every mutation. `all-test-mutations.json` preserves all 68 proofs; `chart-replacement-transcript.txt` preserves this round's failures, restored passes, coverage tables, and formatter output. `chart-replacement-summary.json` records exact metrics and the 154-case audit. Earlier proofs remain in `break-and-revert.txt` and prior transcripts.
- Formatted the changed Python file using `black --line-length 100`. The required repository-wide Black command and CI's command both passed across **398 files**, using the documented single-worker/selector-polling sandbox workaround. The summary includes its helper source; formatter behavior was unchanged.
- CI's `ruff check --output-format github --extend-exclude .workflows-lib .` and `git diff --check` passed.
- Published starting head `7215c74` has a [green Gate run](https://github.com/stranske/Counter_Risk/actions/runs/40860199734). This round's four new cases still require publication and CI; local success is not a CI claim. The Windows cases exercise COM orchestration with controlled mocks, not a live Office installation.

## Production bug fixed earlier in this PR

Commit `0777d42` changes only the row-date predicate in `_extract_prior_populated_series_by_sheet`: a non-date footer previously replaced the last dated row, erasing the prior populated-series set used to detect dropped positions. The real-workbook regression fails with the old predicate and passes with `_coerce_historical_row_date`. No additional production change was made this round. The new code introduces no caches; no negative-cache bug was found in the covered paths.

## Delivery

The workspace's `.git` directory is read-only: staging fails creating `.git/index.lock`. Verified source changes are preserved in an isolated commit under `/tmp/1217-chart.git` and a handoff patch at `/tmp/1217-chart.patch`. Automatic approval review rejected GitHub publication, this reconciled PR-body update, the blocker comment, and the `needs-human` label because **MCP tool call requires approval, but approval policy is never**. The live checkboxes remain stale; a runner with publication access must publish the patch and apply this body. This round's changes are unpushed. PR #1217 is open and ready for review (`isDraft=false`).

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
