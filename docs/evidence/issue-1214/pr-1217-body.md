## Summary

- Add CLI discovery, GUI callback, settings, and failure-reporting tests, plus focused pipeline orchestration, historical-workbook, screenshot, and Office failure coverage.
- This round adds five cases for historical workbook-open errors and recovery after malformed series headers. It verifies exception type/cause/path, continuation to readable worksheets, header trimming and order, and workbook closure.
- No production change in this round. The PR's only production change is the earlier one-line historical-footer fix described below.

## Target selection and contract reconciliation

[Issue #1214](https://github.com/stranske/Counter_Risk/issues/1214) ranks CLI first (one escaped-defect signal, churn 1, 19 CI uncovered units), then pipeline (churn 15, 302 CI uncovered units). CLI is fully covered locally, so this round continues with pipeline. The reserved GUI runner is untouched.

The audit of all three PR-added test modules matches **133 collected cases to 59 executed mutations**, with no omissions, duplicate proofs, or uncollected cases. All recorded mutated exits are 1 and restored exits are 0. This reconciles nested contract items 1–5: ranked selection, executed break-and-revert proofs, a minimal fix for the one real bug found, low blast radius, and one existing PR. The corresponding local checkboxes below are checked; publishing their remote update is blocked.

## Coverage

The authoritative issue baseline remains **89.32% blended CI coverage**. Local configuration measures lines only; target-limited reports over the whole non-slow suite do not establish a blended CI reduction.

| Target | Existing tests, before PR | With all PR tests | Missing lines |
|---|---:|---:|---:|
| `src/counter_risk/cli/__init__.py` | 218/237 (91.98%) | 237/237 (100.00%) | 19 -> 0 |
| `src/counter_risk/pipeline/run.py` | 2334/2636 (88.54%) | 2535/2636 (96.17%) | 302 -> 101 |

The earlier existing-tests baseline excludes the PR's three added modules and uses the final production source. Across the PR, local missing lines decrease by **220** (19 CLI + 201 pipeline). This round adds **two** covered lines (5716 and 5765), changing pipeline coverage from 2533/2636 (96.09%, 103 missing) to 2535/2636 (96.17%, 101 missing). Exact summaries are in `historical-header-recovery-summary.json`.

CLI has no remaining local missing lines. Pipeline still has 101, including invalid-data guards, alternative output backends, and filesystem/Office failure paths. These are further test candidates, not declared untestable. The approximately 180-unit blended CI reduction remains unverified: its shortfall cannot be calculated from local line-only reports, so conservatively up to 180 CI units remain unconfirmed. This is a bounded partial delivery pending publication and comparable Gate coverage.

## Verification

- Stable final: `COVERAGE_FILE=/tmp/1217-header-final.cov pytest tests/ --cov=counter_risk.pipeline.run --cov=counter_risk.cli --cov-report=term-missing --cov-report=json:/tmp/1217-header-final.json -m "not slow" -q -o addopts=`: **2611 passed, 1 skipped, 87 deselected**, 169.10s, exit 0.
- Required targeted check: `COVERAGE_FILE=/tmp/1217-header-targeted.cov pytest tests/pipeline/test_run_coverage_round.py --cov=counter_risk.pipeline.run --cov-report=term-missing --cov-report=json:/tmp/1217-header-targeted.json -m "not slow" -q -o addopts=`: **118 passed**, 1.44s, exit 0. The standalone target module's Cover column is **38%**; the comparable whole-suite pipeline result is **96.17%** above.
- The initial current-round run had 2605 passed, one failed, one skipped. Editing a candidate test during the run changed collection between the CI-partition check's subprocesses, causing that failure. Its target coverage matches the previous green round's 2533/2636. It is not claimed as a green baseline; the stable final run above resolves the collection race.
- Earlier existing-tests baseline: `pytest tests/ --ignore=tests/pipeline/test_run_link_refresh_failures.py --ignore=tests/pipeline/test_run_coverage_round.py --ignore=tests/test_cli_coverage_round.py --cov=counter_risk.pipeline.run --cov=counter_risk.cli --cov-report=term-missing -m "not slow" -q`: **2478 passed, 1 skipped, 87 deselected**.
- Published-head Gate [40847909230](https://github.com/stranske/Counter_Risk/actions/runs/40847909230) succeeded at `63f9dacede6cc4f923169cbc113fa2871c98723c`. Python 3.14 job `123360109439` reports **2579 passed, 1 skipped**, `COVERAGE_ENABLED=false`, and `COVERAGE_MIN_OUTCOME=skipped`. The five newest local cases still need publication and CI.
- Ran `black --line-length 100 tests/pipeline/test_run_coverage_round.py`. Both repository-wide checks exited 0 across **398 files**: `black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .` and CI's `black --check --line-length 100 --exclude '(\.venv|\.workflows-lib|node_modules)' .`. The ordinary command hung and was interrupted; as in earlier rounds, `BLACK_NUM_WORKERS=1` and a temporary `sitecustomize` limiting `EpollSelector.select` waits to 0.1 seconds let both commands finish without changing formatting behavior.
- `ruff check --output-format github --extend-exclude .workflows-lib .` and `git diff --check` passed.

## Break-and-revert proof

`all-test-mutations.json` records **59 executed mutations covering all 133 collected cases**. `break-and-revert.txt` preserves the commands, failures, passing restorations, and final/targeted console output.

This round executes two mutations: propagating raw workbook-open errors makes all three KeyError/ValueError/OSError cases fail; propagating raw series-header errors instead of skipping the malformed worksheet makes both column-count/header-cell cases fail. All five pass after restoration. The source SHA256 is identical before and after, and no production diff remains from the mutations.

## Production bug fixed earlier in this PR

Commit `0777d42` changes only the row-date predicate in `_extract_prior_populated_series_by_sheet`: a non-date footer previously replaced the last dated row, erasing the prior populated-series set used to detect dropped positions. The real-workbook regression test fails with the old predicate and passes with `_coerce_historical_row_date`. No additional production defect was found in this round. The final full non-slow suite passes.

## Delivery blockers

- After verification, `git add` failed with `fatal: Unable to create .git/index.lock: Read-only file system`; local commit/push are unavailable.
- Automatic approval review rejected publication through GitHub `create_tree`: **MCP tool call requires approval, but approval policy is never**. Verified changes and the replacement PR body are preserved locally for automation handoff.
- Automatic approval review also rejected the PR-body update, blocker comment, and `needs-human` label with the same approval-policy restriction. The remote body and checkboxes remain unchanged; `historical-header-recovery-summary.json` records each result.
- PR #1217 remains the sole PR for this chunk. Its last readback is open and ready for review (`isDraft=false`) at `63f9dacede6cc4f923169cbc113fa2871c98723c`.

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
