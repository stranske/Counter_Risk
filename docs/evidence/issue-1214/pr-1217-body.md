## Summary

- Add discriminating CLI discovery, GUI callback, settings, and failure-reporting tests.
- Add pipeline stage-failure, workbook-recovery, historical-series, and link-refresh failure/cleanup coverage. Add seven output-validation cases covering incomplete Drop-In inputs and invalid Master PPT/PDF output counts.
- Fix the previously discovered historical-footer bug with a one-line row-date predicate change; this run adds tests only.

## Task reconciliation

- Reviewed commits `5e49832`, `0777d42`, `ec7ee71`, and `aedfd82`, and `16b0262`, including their source diff and mutation evidence.
- Target selection follows issue #1214's ranking: CLI first (1 escaped-defect signal, churn 1, 19 CI uncovered units), then pipeline (churn 15, 302 CI uncovered units). The reserved GUI runner file is untouched.
- Nested contract items 1–5 are verified locally: ranked selection, executed mutation proof for every added case, the minimal historical-footer fix, scoped changes, and one existing PR. Their reconciled checkboxes are below.
- Delivery, CI, and the Gate/PR-body acceptance remain unchecked for the current edits: repository metadata is read-only and connector writes require unavailable approval. Remote checkboxes remain stale.

## Coverage

Issue #1214's authoritative baseline remains **89.32% blended CI coverage**, with 19 uncovered CLI units and 302 pipeline units. Local configuration measures lines only; the following comparison does not establish a blended CI reduction.

Both local runs exercise the whole non-slow suite against the same final production source. The baseline reproduces the issue's per-target missing counts (19 CLI, 302 pipeline). The PR reduces local missing lines by **200** (19 CLI + 181 pipeline), exceeding 180 in this local line-only comparison; comparable Gate confirmation is still pending. The existing-tests baseline excludes this PR's three added test modules; the final run includes them.

| Target | Existing tests | With PR tests | Missing lines |
|---|---:|---:|---:|
| `src/counter_risk/cli/__init__.py` | 218/237 (91.98%) | 237/237 (100.00%) | 19 -> 0 |
| `src/counter_risk/pipeline/run.py` | 2334/2636 (88.54%) | 2515/2636 (95.41%) | 302 -> 121 |

- The requested approximately 180-unit CI reduction remains unverified; its authoritative shortfall cannot be calculated from a local line-only report. Conservatively, up to 180 CI units remain unconfirmed until comparable Gate results exist.
- CLI is fully covered locally. Pipeline still has 121 uncovered lines, including invalid-data guards, alternative output backends, and filesystem/Office failure paths. Further discriminating tests are needed for those cases; they are not claimed to be untestable. This is a partial delivery pending publication and Gate results.
- An attempted per-test attribution was discarded: coverage warns that dynamic contexts are unsupported with the configured `sysmon` backend. No context-derived gains are claimed. The table uses only line totals from separate runs.

## Verification

- This follow-up baseline, before the seven new cases: `COVERAGE_FILE=/tmp/1217-round-baseline.cov pytest tests/ --cov=counter_risk.pipeline.run --cov=counter_risk.cli --cov-report=term-missing --cov-report=json:/tmp/1217-round-baseline.json -m "not slow" -q -o addopts=`: **2588 passed, 1 skipped, 87 deselected** in 138.29 seconds; CLI 237/237 (100%), pipeline 2510/2636 (95.22%).
- This follow-up final full suite: `COVERAGE_FILE=/tmp/1217-round-final.cov pytest tests/ --cov=counter_risk.pipeline.run --cov=counter_risk.cli --cov-report=term-missing --cov-report=json:/tmp/1217-round-final.json -m "not slow" -q -o addopts=`: **2595 passed, 1 skipped, 87 deselected** in 124.16 seconds; CLI 237/237 (100%), pipeline 2515/2636 (95.41%). New tests cover five additional previously missing lines: 2726, 2732, 2734, 2888, and 3969.
- Targeted module verification: `COVERAGE_FILE=/tmp/1217-output-contracts.cov pytest tests/pipeline/test_run_coverage_round.py --cov=counter_risk.pipeline.run --cov-report=term-missing -m "not slow" -q -o addopts=`: **102 passed**; standalone pipeline coverage is 36%, not the whole-suite figure.
- Published-head Gate [40837070799](https://github.com/stranske/Counter_Risk/actions/runs/40837070799) succeeded at `16b0262357d4caba9b3ff17e76bd88a4a63639a8`. Python 3.14 job `123324431857` reports **2561 passed, 1 skipped**, `COVERAGE_ENABLED=false`, and `COVERAGE_MIN_OUTCOME=skipped`. This verifies the published tests passed, but supplies no current coverage measurement. The seven new local cases still require publication and CI.
- Both repository-wide Black checks and Ruff passed again after this follow-up. The unmodified Black command stalled in this sandbox; the same temporary selector-wait cap described below allowed both complete 398-file checks to finish.

Earlier-round verification retained for the full PR comparison:

- Existing-tests baseline: `COVERAGE_FILE=/tmp/1217-existing-tests.cov pytest tests/ --ignore=tests/pipeline/test_run_link_refresh_failures.py --ignore=tests/pipeline/test_run_coverage_round.py --ignore=tests/test_cli_coverage_round.py --cov=counter_risk.pipeline.run --cov=counter_risk.cli --cov-report=term-missing --cov-report=json:/tmp/1217-existing-tests-coverage.json -m "not slow" -q`: **2478 passed, 1 skipped, 87 deselected**, in 188.34 seconds.
- Final full suite: `COVERAGE_FILE=/tmp/1217-final.cov pytest tests/ --cov=counter_risk.pipeline.run --cov=counter_risk.cli --cov-context=test --cov-report=term-missing --cov-report=json:/tmp/1217-final-coverage.json -m "not slow" -q`: **2588 passed, 1 skipped, 87 deselected**, in 184.07 seconds. Line coverage is valid; unsupported dynamic-context attribution is unused.
- New module: `pytest tests/pipeline/test_run_link_refresh_failures.py --cov=counter_risk.pipeline.run --cov-report=term-missing -m "not slow" -q`: **5 passed**. This targeted module's standalone 12% pipeline coverage is not the full-suite result.
- `ruff check --output-format github --extend-exclude .workflows-lib .` passed.
- Both Black gates passed across **398 files**: `black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .` and CI's `black --check --line-length 100 --exclude '(\.venv|\.workflows-lib|node_modules)' .`. As in the prior round, `BLACK_NUM_WORKERS=1` and a temporary runtime helper cap selector waits at 0.1 seconds to keep Black responsive in this sandbox; formatter behavior is unchanged.

## Break-and-revert proof

- `docs/evidence/issue-1214/all-test-mutations.json` now records **49 executed mutations covering all 117 collected cases** across this PR's three added modules. The recorded case names exactly match pytest collection, with no duplicates or omissions.
- This follow-up's five mutations made all seven new cases fail (pytest exit 1), then pass after restoration (exit 0): silently skip configured Drop-In output when parsed inputs, the All Programs variant, or totals are absent; accept zero/multiple Master PPT outputs; and silently select the first of multiple PDFs. The transcript records failures and restorations, including a matching source SHA256 before/after.
- The earlier round's four mutations covered all five link-refresh cases: remove preparation-error cause chaining, report a missing Office client as success, omit individual linked-shape updates, and omit saving the presentation.
- `docs/evidence/issue-1214/break-and-revert.txt` contains the executed commands, failures, and passing restorations. All source mutations were restored before the final suite; this run leaves no production diff.

## Production bug fixed in the earlier round

Commit `0777d42` changed only the row-date predicate in `_extract_prior_populated_series_by_sheet`: a non-date footer previously replaced the last dated row, erasing the prior populated-series set used to detect dropped positions. The real-workbook regression test fails with the old predicate and passes with `_coerce_historical_row_date`; the final full non-slow suite passes with the fix. No additional production defect was found in this run.

## Delivery blockers

- The requested commit was attempted after test and formatting checks. Staging failed: `fatal: Unable to create .git/index.lock: Read-only file system`. No commit or push was possible; verified edits remain in the workspace for the automation handoff.
- The GitHub connector rejected the PR-body update, blocker comment, and `needs-human` label: **MCP tool call requires approval, but approval policy is never**. This file is the concrete replacement PR body; it has not been published remotely.
- Final PR readback: #1217 is **open**, `isDraft=false`, at `16b0262357d4caba9b3ff17e76bd88a4a63639a8`. No new PR was created.

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
