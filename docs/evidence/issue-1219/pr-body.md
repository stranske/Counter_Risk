## Summary

Add discriminating tests for all eight issue-ranked targets in the prescribed order. Production code is unchanged; no real bug was demonstrated. The latest follow-up strengthens the first-ranked target, `web_demo.py`: the public runner rejects optional cash inputs, screenshots, and discovery roots whose paths appear inside fixtures but resolve through symlinks to external data. Validation must happen before the pipeline runs or existing artifacts are changed.

This is a partial coverage delivery. The issue's **89.32% blended CI baseline / 185 missing ranked units** remains authoritative. Current project configuration explicitly uses line-only coverage (`branch=false`), so local results cannot establish the requested CI blended reduction.

## Verification

- Latest full local suite, Python 3.14.9: **2,559 passed, 1 skipped**, in 97.95s. Command: `pytest tests/ -n 4 -m 'not slow' -q -o addopts= --cov=counter_risk --cov-report=json:/tmp/issue-1219-symlink-full.json --cov-report=term`. Overall local line coverage is **90.7744%**. [Full output](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/symlink-full-suite.log).
- Latest targeted command: `pytest tests/test_web_demo_helpers.py tests/test_web_demo_smoke.py -m 'not slow' -q -o addopts= --cov=counter_risk.web_demo --cov-report=term-missing`: **15 passed, 1 deselected**; `web_demo.py` **100% (117/117 statements)** before and after these three cases.
- Previous focused/adjacent suites: **353 passed, 14 deselected**, with eight explicit module coverage options; see [targeted.log](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/targeted.log).
- Ruff passes with CI flags: `ruff check --output-format github --extend-exclude .workflows-lib .`. `git diff --check` passes.
- Black 26.10.1: changed file passes the ordinary formatting command; all **403 Python files** pass the required `--check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .` flags. The native repository-wide CLI fails creating its multiprocessing forkserver socket in this sandbox; its single-worker scheduler did not finish promptly. The successful check preserves Black's CLI, discovery and formatting rules, replacing only the scheduler with serial calls to Black's own `reformat_one`. [Black output](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/symlink-black.log).
- Published head `67929e5` has passing [Gate](https://github.com/stranske/Counter_Risk/actions/runs/40839922611) and [Agents Guard](https://github.com/stranske/Counter_Risk/actions/runs/40839922122) statuses. These statuses precede the latest three symlink cases; hosted checks for those cases are unverified.

## Real break-and-revert proof

All **55 added test functions / 81 unique parameter cases** have actual mutation proof:

- [Original receipts](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/mutation-receipts.json) and [transcript](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/mutation-transcript.txt): 53 functions / 76 cases. Each corresponding mutation fails with exit 1; the restored run passes with exit 0. MOSERS checks include seeded stale-row clearing, section boundaries, and complete missing-sheet diagnostics.
- [Runtime-transition receipts](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/followup-mutation-receipts.json): one function / two cases. Omitting the runtime check, ignoring preloaded state, publishing before validation, and omitting offline mode before pipeline execution each cause corresponding failures; restored runs pass.
- [Symlink receipts](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/symlink-mutation-receipts.json) and [transcript](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/symlink-mutation-transcript.txt): one function / three cases. Preserving symlinks instead of resolving absolute source paths causes **3 failures**. Individually omitting cash, screenshot, or discovery inputs causes **1 corresponding failure each**. Every restored run passes all three cases. Source bytes match their original SHA-256 after every experiment.

## Coverage and partial delivery

Local whole-suite counts use the same source configuration and `-m 'not slow'`. The baseline excludes the eight PR-added test modules. Its overall line coverage is **68.9506%**, versus **90.7744%** for the candidate. The difference is dominated by unrelated module coverage and is sensitive to import/collection order; it must not be attributed wholesale to this PR. [Baseline output](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/baseline.log) and [per-file summaries](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/coverage-summary.json).

| Target, in issue ranking order | Baseline missed lines | Candidate missed lines | Candidate line coverage |
| --- | ---: | ---: | ---: |
| `web_demo.py` | 0 | 0 | 100.00% |
| `mosers/workbook_generation.py` | 0 | 0 | 100.00% |
| `parsers/repo_cash_sources.py` | 1 | 1 | 99.44% |
| `compute/limits.py` | 1 | 1 | 99.46% |
| `pipeline/data_quality.py` | 6 | 1 | 99.62% |
| `chat/context.py` | 4 | 4 | 97.04% |
| `chat/session.py` | 0 | 0 | 100.00% |
| `demo_artifact.py` | 0 | 0 | 100.00% |

Only **5 fewer missed target lines** are measured locally, **175 short** of approximately 180. This follow-up adds **zero** covered lines. CI blended coverage reduction remains unverified.

Remaining paths: `repo_cash_sources.py:192` handles `None` from `csv.DictReader`, which normal iteration does not yield; `limits.py:211` checks an empty validated limit list despite schema validation requiring entries; `data_quality.py:494` is a category fallback already handled by the code-to-category mapping; `context.py:16-22` covers alternate optional-PyArrow import shapes absent locally. The other four targets have no missed lines in the local whole-suite run. No fake runtime states, source refactors, exclusions, or threshold changes were introduced to force those defensive paths into the metric. The local above-90 measurement includes existing PR tests and is not a pre-initiative CI baseline.

## Publication blocker

The existing PR is open and ready for review (`draft=false`) at `67929e5`. Its live body still describes only the first two targets. This file is the reconciled replacement body. The latest three symlink cases and their evidence are verified locally but remain unpublished: `git add` cannot create `.git/index.lock` because the primary checkout's Git metadata is read-only. A GitHub `create_tree` attempt was rejected with `MCP tool call requires approval, but approval policy is never`; no remote branch or PR body was changed. A portable commit and bundle preserve the follow-up under `/tmp/issue-1219-symlink-publication/`. Primary-checkout staging, publication, hosted checks for this follow-up, and live checkbox reconciliation remain incomplete.

## Verified contract

- [x] Pick targets by the issue's escaped-defect/churn/uncovered-mass ranking, beginning with `web_demo.py`.
- [x] Run real break-and-revert proof for every added test case and record both results.
- [x] Review possible bugs without working around demonstrated defects; no production bug was found and no production source is changed.
- [x] Keep the diff focused on target tests and verification evidence, without refactors.
- [x] Keep this logical chunk in one existing ready-for-review PR, #1221.
- [x] Disclose the authoritative CI baseline, differing local metric, partial shortfall, and remaining target paths.
- [x] Run formatter and linter checks with CI flags; disclose the serial Black scheduler workaround.
- [ ] Publish the latest symlink tests/evidence and run hosted checks for that follow-up.

Closes #1219
