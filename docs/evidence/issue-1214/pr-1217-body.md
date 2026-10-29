## Summary

- Add CLI discovery, GUI callback, settings, and failure-reporting tests, plus focused pipeline orchestration, historical-workbook, screenshot, and Office failure coverage.
- This round adds three static-distribution cases for failed slide export, deck rebuild, and external-link removal. Each verifies a warning retaining the failure detail, no returned deliverable, preserved source bytes, and no later stage calls.
- No production change in this round. The PR's only production change is the earlier one-line historical-footer fix described below.

## Target selection and contract reconciliation

[Issue #1214](https://github.com/stranske/Counter_Risk/issues/1214) ranks CLI first (one escaped-defect signal, churn 1, 19 CI uncovered units), then pipeline (churn 15, 302 CI uncovered units). CLI is fully covered locally, so this round continues with pipeline. The reserved GUI runner is untouched.

Reviewed recent commits through `f76abc5` and audited all three PR-added test modules: **136 collected cases match 60 executed mutations**, without omissions, duplicates, or uncollected cases. All recorded mutated exits are 1 and restored exits are 0. This verifies nested contract items 1–5: ranked selection, executed break-and-revert proofs, a minimal fix for the one real bug found, low blast radius, and one existing PR. Their local checkboxes below are checked; automatic approval review rejected the remote reconciliation update.

## Coverage

The authoritative issue baseline remains **89.32% blended CI coverage**. Local configuration measures lines only; target-limited reports over the whole non-slow suite do not establish a blended CI reduction.

| Target | Existing tests, before PR | With all PR tests | Missing lines |
|---|---:|---:|---:|
| `src/counter_risk/cli/__init__.py` | 218/237 (91.98%) | 237/237 (100.00%) | 19 -> 0 |
| `src/counter_risk/pipeline/run.py` | 2334/2636 (88.54%) | 2538/2636 (96.28%) | 302 -> 98 |

The earlier existing-tests baseline excludes the PR's three added modules and uses the final production source. Across the PR, local missing lines decrease by **223** (19 CLI + 204 pipeline). This round adds **three** covered lines (3938–3940), changing pipeline coverage from 2535/2636 (96.17%, 101 missing) to 2538/2636 (96.28%, 98 missing). Exact summaries are in `static-distribution-failures-summary.json`.

CLI has no remaining local missing lines. Pipeline still has 98, including invalid-data guards, alternative output backends, and filesystem/Office failure paths. These are further test candidates, not declared untestable. The approximately 180-unit blended CI reduction remains unverified: its shortfall cannot be calculated from local line-only reports, so conservatively up to 180 CI units remain unconfirmed. This is a bounded partial delivery pending publication and comparable Gate coverage.

## Verification

- Full non-slow suite: `COVERAGE_FILE=/tmp/1217-static-full.cov pytest tests/ --cov=counter_risk.pipeline.run --cov=counter_risk.cli --cov-report=term-missing --cov-report=json:/tmp/1217-static-full.json -m "not slow" -q -o addopts=`: **2614 passed, 1 skipped, 87 deselected**, 230.64s, exit 0.
- Required targeted check: `COVERAGE_FILE=/tmp/1217-static-targeted.cov pytest tests/pipeline/test_run_coverage_round.py --cov=counter_risk.pipeline.run --cov-report=term-missing --cov-report=json:/tmp/1217-static-targeted.json -m "not slow" -q -o addopts=`: **121 passed**, 1.79s, exit 0. The standalone test module's pipeline Cover column is **39%**; the comparable whole-suite result is **96.28%** above.
- Earlier existing-tests baseline: `pytest tests/ --ignore=tests/pipeline/test_run_link_refresh_failures.py --ignore=tests/pipeline/test_run_coverage_round.py --ignore=tests/test_cli_coverage_round.py --cov=counter_risk.pipeline.run --cov=counter_risk.cli --cov-report=term-missing -m "not slow" -q`: **2478 passed, 1 skipped, 87 deselected**.
- Published-head Gate [40851726293](https://github.com/stranske/Counter_Risk/actions/runs/40851726293) succeeded at `f76abc5c3cd581b0e8618c27ddc196ae03c45cd3`. Python 3.14 job `123372866760` reports **2584 passed, 1 skipped**, `COVERAGE_ENABLED=false`, and `COVERAGE_MIN_OUTCOME=skipped`. The three newest cases still need publication and CI.
- Ran `black --line-length 100 tests/pipeline/test_run_coverage_round.py`. Both repository-wide checks passed across **398 files**: `black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .` and CI's `black --check --line-length 100 --exclude '(\.venv|\.workflows-lib|node_modules)' .`. The ordinary command stalled and timed out after 25s; as in earlier rounds, both commands passed with `BLACK_NUM_WORKERS=1` and a temporary `sitecustomize` bounding `EpollSelector.select` waits to 0.1 seconds. Formatter behavior was unchanged.
- `ruff check --output-format github --extend-exclude .workflows-lib .` and `git diff --check` passed.

## Break-and-revert proof

`all-test-mutations.json` records **60 executed mutations covering all 136 collected cases**. `break-and-revert.txt` preserves the commands, failures, passing restorations, and full-suite output.

This round suppresses the static-distribution failure warning: all three export/rebuild/scrub failure cases fail (exit 1). After restoring the warning, all three pass (exit 0). The production source SHA256 is identical before and after, and no production mutation diff remains.

## Production bug fixed earlier in this PR

Commit `0777d42` changes only the row-date predicate in `_extract_prior_populated_series_by_sheet`: a non-date footer previously replaced the last dated row, erasing the prior populated-series set used to detect dropped positions. The real-workbook regression test fails with the old predicate and passes with `_coerce_historical_row_date`. No additional production defect was found in this round. The final full non-slow suite passes.

## Delivery blockers

- Workspace `git add` failed: `.git/index.lock: Read-only file system`. A separate local Git directory under `/tmp` preserves a commit of the verified source and evidence; `/tmp/1217-static-distribution.patch` is the handoff patch. The workspace branch cannot be advanced here.
- Git transport is unavailable: `git ls-remote` failed with `Could not resolve host: github.com`, so pushing the isolated commit is unavailable.
- Automatic approval review rejected the PR-body reconciliation, blocker comment, and `needs-human` label: **MCP tool call requires approval, but approval policy is never**. The replacement body and checked contract items are preserved locally; the remote body remains unchanged.
- PR #1217 remains the sole PR for this chunk, open and ready for review (`isDraft=false`) at `f76abc5c3cd581b0e8618c27ddc196ae03c45cd3`.

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
