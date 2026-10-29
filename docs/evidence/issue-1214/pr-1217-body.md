## Summary

- Add discriminating CLI discovery, GUI callback, settings, and failure-reporting tests.
- Add pipeline stage-failure, workbook-recovery, historical-series, link-refresh, and output-validation coverage. This round adds four cases for absent Master generators and refresh-fallback failures, including empty error details.
- The only production change is the earlier one-line historical-footer bug fix. This round adds tests and verification evidence.

## Task reconciliation

- Reviewed commits `5e49832`, `0777d42`, `ec7ee71`, `aedfd82`, `16b0262`, and `6243688`, including source changes and mutation records.
- Issue #1214 ranks CLI first (one escaped-defect signal, churn 1, 19 CI uncovered units), then pipeline (churn 15, 302 CI uncovered units). CLI is fully covered locally, so this round continues with pipeline. The reserved GUI runner remains untouched.
- Before implementing this round, matched all 117 previously added cases to 49 executed mutations, with no duplicates or omissions. Nested contract items 1–5 are verified; their reconciled checkboxes are below.
- Attempted the required PR-body reconciliation before continuing. The GitHub connector rejected it because writes require approval and this run's approval policy is `never`. This file preserves the replacement body; remote checkboxes remain stale.

## Coverage

Issue #1214's authoritative baseline remains **89.32% blended CI coverage**. Local configuration measures lines only; these target-limited reports over the whole non-slow suite do not establish a blended CI reduction.

The existing-tests baseline excludes this PR's three added test modules and reproduces the issue's target missing counts. The final suite includes them. Both use the final production source. Across the PR, local missing lines decrease by **206** (19 CLI + 187 pipeline).

| Target | Existing tests | With PR tests | Missing lines |
|---|---:|---:|---:|
| `src/counter_risk/cli/__init__.py` | 218/237 (91.98%) | 237/237 (100.00%) | 19 -> 0 |
| `src/counter_risk/pipeline/run.py` | 2334/2636 (88.54%) | 2521/2636 (95.64%) | 302 -> 115 |

- This round changes pipeline coverage from 2515/2636 (95.41%, 121 missing) to 2521/2636 (95.64%, 115 missing), adding **6** covered lines. Exact line numbers and both report summaries are in `generator-fallback-summary.json`.
- CLI remains fully covered locally. Pipeline still has 115 uncovered lines, including invalid-data guards, alternative output backends, and filesystem/Office failure paths. They need additional discriminating tests and are not claimed to be untestable.
- The approximately 180-unit CI reduction remains unverified. Its exact shortfall cannot be calculated from local line-only reports; conservatively, up to 180 CI units remain unconfirmed. This is a partial delivery pending publication and comparable Gate results.

## Verification

- Current-round baseline: `COVERAGE_FILE=/tmp/1217-next-baseline.cov pytest tests/ --cov=counter_risk.pipeline.run --cov=counter_risk.cli --cov-report=term-missing --cov-report=json:/tmp/1217-next-baseline.json -m "not slow" -q -o addopts=`: **2595 passed, 1 skipped, 87 deselected**, 147.72s.
- Current-round final: `COVERAGE_FILE=/tmp/1217-next-final.cov pytest tests/ --cov=counter_risk.pipeline.run --cov=counter_risk.cli --cov-report=term-missing --cov-report=json:/tmp/1217-next-final.json -m "not slow" -q -o addopts=`: **2599 passed, 1 skipped, 87 deselected**, 130.97s. Actual target coverage is in the table above.
- Required targeted verification: `COVERAGE_FILE=/tmp/1217-generator-targeted.cov pytest tests/pipeline/test_run_coverage_round.py --cov=counter_risk.pipeline.run --cov-report=term-missing -m "not slow" -q -o addopts=`: **106 passed**, pipeline **37%** in this standalone module. This standalone percentage is not the whole-suite result.
- Earlier existing-tests baseline: `COVERAGE_FILE=/tmp/1217-existing-tests.cov pytest tests/ --ignore=tests/pipeline/test_run_link_refresh_failures.py --ignore=tests/pipeline/test_run_coverage_round.py --ignore=tests/test_cli_coverage_round.py --cov=counter_risk.pipeline.run --cov=counter_risk.cli --cov-report=term-missing --cov-report=json:/tmp/1217-existing-tests-coverage.json -m "not slow" -q`: **2478 passed, 1 skipped, 87 deselected**, 188.34s.
- Published-head Gate [40843822529](https://github.com/stranske/Counter_Risk/actions/runs/40843822529) succeeded at `62436883c9a64dabd92c7ad789c39ccac6b60009`. Python 3.14 job `123346586079` reports **2568 passed, 1 skipped**, `COVERAGE_ENABLED=false`, and `COVERAGE_MIN_OUTCOME=skipped`. It verifies the published tests passed but supplies no current coverage measurement. This round's four local cases still require publication and CI.
- `ruff check --output-format github --extend-exclude .workflows-lib .` passed.
- Both repository-wide Black checks passed across **398 files**: `black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .` and CI's `black --check --line-length 100 --exclude '(\.venv|\.workflows-lib|node_modules)' .`. Ran Black on the changed test file first. The unmodified repository-wide check stalled in this sandbox; `BLACK_NUM_WORKERS=1` and a temporary runtime helper limiting selector waits to 0.1 seconds allowed both checks to finish, with formatter behavior unchanged.

## Break-and-revert proof

- `all-test-mutations.json` records **51 executed mutations covering all 121 collected cases** across the PR's three added modules, with no duplicate or omitted cases. All recorded mutated exits are 1 and restored exits are 0.
- This round's first mutation removes the no-Master early return. Both new absent-Master cases fail, then pass after restoration. They check preserved workbook bytes and output paths, retained auxiliary output paths, skipped PPT status, and no later refresh/distribution stages.
- The second mutation skips the enabled refresh fallback. Both failure-detail cases fail, then pass after restoration. They check the attempted refresh, failed Master status, skipped distribution, exact warning text, and absence of distribution artifacts.
- `break-and-revert.txt` records executed commands, failures, and passing restorations. Both mutations record matching source SHA256 values before and after; this round leaves no production diff.

## Production bug fixed in the earlier round

Commit `0777d42` changes only the row-date predicate in `_extract_prior_populated_series_by_sheet`: a non-date footer previously replaced the last dated row, erasing the prior populated-series set used to detect dropped positions. The real-workbook regression test fails with the old predicate and passes with `_coerce_historical_row_date`. The final full non-slow suite passes. No additional production defect was found in this round.

## Delivery blockers

- Staging was attempted after the targeted tests, mutation checks, Black, and Ruff passed. It failed with `fatal: Unable to create .git/index.lock: Read-only file system`. Commit/push are unavailable; verified edits remain in the workspace for automation handoff.
- The GitHub connector rejected the PR-body update, blocker comment, and `needs-human` label: **MCP tool call requires approval, but approval policy is never**. This replacement body has not been published remotely.
- PR readback: #1217 is **open**, `isDraft=false`, at `62436883c9a64dabd92c7ad789c39ccac6b60009`. No new PR was created.

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
- [ ] The PR's Gate coverage shows the targets' uncovered statements+branches down by about 180 or more, or the PR body states how far short it is and why and explains each target that could not be meaningfully covered (a partial PR meets this criterion; no PR does not).
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
