## Summary

Add 87 regression cases across ten test modules in issue #1218's escaped-defect/churn/uncovered-mass order. Tests cover NISA parsing, rollups, runner launch handling, mapping-diff output, provider fallback, normalization, limits configuration, PowerPoint relationship repair, and XLSM building. No production bug was found; production files are byte-identical to the PR base.

Reconciliation: reviewed `3456860`, `edc500f`, `0054b34`, `d843da8`, `e7a1c32`, and `9cc0e39`. The former PR body described only the initial parser-boundary tests. The committed coverage summary and 71 mutation scenarios support all five nested contract checkboxes. Gate run [40843725927](https://github.com/stranske/Counter_Risk/actions/runs/40843725927) passed at `9cc0e39`, including Python 3.13 and 3.14 pytest jobs. This remains one ready-for-review PR for the existing coverage chunk, whose initial baseline was below 90%.

## Incomplete-worksheet regression

Four new real-XLSX cases verify that an earlier worksheet missing a required header cannot displace a later complete worksheet. The decoy has real data, an alphabetically earlier name, and earlier headers. Cases cover missing cash and missing two-line annualized-volatility headers, with both worksheet orders. Assertions verify counterparties, notionals, cash, and volatility through the public parser.

Executed the break-and-revert check in an isolated checkout: changed `_find_header_row_and_columns` to falsely return an empty missing-header tuple, admitting the decoy. All four cases failed (pytest exit 1); exact source restoration made all four pass (exit 0). `completeness-mutation-receipt.json` records the exact edit, command, per-case outcomes, outputs, and matching original/restored SHA-256 values. No production change or additional covered statement is claimed for this follow-up.

## Coverage

Matched whole-suite measurements on Python 3.14.9, using `python -m pytest tests/ -m "not slow" -n 4 --dist load --cov=counter_risk --cov-report=term --cov-report=json:<output>`:

- PR base `faad152`: **2,478 passed, 1 skipped**, 10,911/12,216 statements covered, **89.3173%**.
- Candidate: **2,565 passed, 1 skipped**, 11,109/12,216 statements covered, **90.9381%**.
- **198 fewer uncovered statements**, all within the issue's ranked targets; no coverage exclusions or thresholds changed.

The measured baseline agrees with the issue's 89.32% rounded figure. The repository actually sets `branch = false`, so these are line-only results, not blended line+branch results. Gate explicitly disables coverage (`pr-00-gate.yml`); there is no Gate coverage artifact to claim. The table below comes from matched local whole-suite runs with the same non-slow selection as main's coverage job.

| Target, in issue order | Missing before | Missing after | Coverage before | Coverage after |
|---|---:|---:|---:|---:|
| parsers/nisa.py | 30 | 2 | 86.24% | 99.08% |
| compute/rollups.py | 16 | 0 | 94.86% | 100% |
| runner_launch.py | 14 | 0 | 92.75% | 100% |
| cli/mapping_diff_report.py | 12 | 1 | 87.76% | 98.98% |
| reports/mapping_diff.py | 12 | 0 | 87.88% | 100% |
| chat/providers/langchain_runtime.py | 9 | 2 | 96.17% | 99.15% |
| normalize.py | 5 | 0 | 95.54% | 100% |
| limits_config.py | 3 | 0 | 94.74% | 100% |
| chat/providers/base.py | 2 | 2 | 98.77% | 98.77% |
| ppt/pptx_postprocess.py | 54 | 0 | 66.46% | 100% |
| build/xlsm.py | 48 | 0 | 60.33% | 100% |

The issue lists 205 gaps; 198 are covered, exceeding its approximate 180-unit goal. Seven defensive statements remain, with these explicit limits:

- NISA lines 239/311 require counterparty inference to receive no header columns, but the public caller first requires all nine numeric headers. Testing them would require bypassing that invariant.
- CLI line 90 requires `payload_items` to be empty after a nonempty `payload_paths` loop that unconditionally appends each loaded payload.
- Runtime lines 191/192 require an empty slot catalog, but configuration loading falls back to three defaults and environment overrides preserve the slots.
- Provider base lines 178/179 repeat the missing-environment error after the same condition has already raised at lines 158–162. This target needed no new tests; it is a redundant defensive branch.

## Break-and-revert evidence

Every added case has executed RED/GREEN evidence. Receipt files in `docs/evidence/issue-1218/` record source edits and matching original/restored hashes:

| Receipt | Mutation scenarios | Distinct cases |
|---|---:|---:|
| `mutation-receipts.json` | 49 | 75 |
| `numeric-mutation-receipts.json` | 17 | 2 |
| `sheet-selection-mutation-receipts.json` | 2 | 4 |
| `segment-mutation-receipts.json` | 3 | 2 |
| `completeness-mutation-receipt.json` | 1 | 4 |

Each scenario failed with the deliberate source change and passed after restoration. No collection errors or skips count as proof. The earlier malformed-XML mutation that changed no observable output was discarded; removing the ParseError catch instead produced a verified failure. The numeric cases assert all 17 numeric mappings with distinct values. Worksheet cases distinguish header-row priority, case-insensitive names, and incomplete-header rejection. Segment cases distinguish first-column and adjacent-column detection and inherited segments.

## Validation

- Whole suite: `COVERAGE_FILE=<isolated data file> python -m pytest tests/ -m "not slow" -n 4 --dist load --cov=counter_risk --cov-report=term --cov-report=json:<output>`: **2,565 passed, 1 skipped** in 163.67 seconds. JSON confirms **11,109/12,216 lines covered (90.9381%)** and 198 fewer missing statements than the matched PR base.
- Focused NISA: `python -m pytest tests/test_nisa_all_programs_parser.py -m "not slow" --cov=counter_risk.parsers.nisa --cov-report=term-missing -q`: **30 passed**, with `nisa.py` showing **99%** in the actual coverage table (216/218 statements; lines 239/311 missing).
- Black **26.10.1**: formatted the changed file at line length 100; required whole-tree check `black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .` passed for **395 files**. A temporary Python startup shim schedules 10ms asyncio wakeups, and `BLACK_NUM_WORKERS=1` avoids sandbox process-pool limits; formatting, parse validation, and exclusions are unchanged. The CI variant adding `\.venv` to the exclusion also passed for 395 files.
- Ruff **0.17.3**: `ruff check --output-format github --extend-exclude .workflows-lib .` passed for the whole tree.
- `git diff --check` passed; all production files match the PR base. Mutation runs used a separate checkout and restored the source exactly.
- Prior published head `9cc0e39` passed Gate on both supported Python versions. The four new cases await publication and hosted CI; the CI acceptance checkbox below remains unchecked for this candidate.

## Delivery limitation

The main checkout's `.git` directory is read-only. The new test changes and evidence are committed in `/tmp/counter-risk-1218-completeness` and exported as `/tmp/counter-risk-1218-completeness.bundle`. GitHub publication is blocked because the sandbox cannot resolve `github.com` (confirmed by a Git push dry run). Automatic approval review rejected both PR-body reconciliation and adding `needs-human`: `MCP tool call requires approval, but approval policy is never`. The reconciled checkboxes are preserved here; they have not been applied to the live PR body. Hosted CI acceptance remains unchecked for the new four cases until publication and a successful CI run.

Closes #1218

<!-- pr-preamble:start -->
<!-- meta:issue:1218 -->
> **Source:** Issue #1218

Closes #1218

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
