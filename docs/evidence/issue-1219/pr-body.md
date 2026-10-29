## Summary

Add discriminating tests for all eight issue-ranked targets in the prescribed order. A follow-up found and fixes a real bug in the first-ranked target, `web_demo.py`: relocating a demo configuration to accommodate a repository-fixture fallback changed the base directory for its other relative inputs. Valid fixture configurations consequently failed validation or passed incorrect paths to the pipeline. Resolve every configured fixture source against the original configuration before writing its relocated copy, including optional cash, raw inputs, screenshots, and discovery roots. A second regression was found in the same first-ranked target: `exposure_summary_xlsx` was absent from both the relocation and fixture-source lists. Its relative paths changed meaning after relocation, and a symlink outside the fixtures reached the pipeline unchecked. Add that field to both lists (two production lines), with two regression parameter cases. Both cases fail before the fix and pass after it. The original YAML remains unchanged. No refactor or unrelated production change is included.

This is a partial coverage delivery. The issue's **89.32% blended CI baseline / 185 missing ranked units** remains authoritative. Current configuration uses line-only coverage (`branch=false`); local results cannot establish the requested CI blended reduction.

The latest test-only follow-up extends the first-ranked target's relocation and fixture-containment regressions to all 15 configured top-level source fields. It adds 25 parameter cases without changing production code. Each new case fails when its own field is removed from the corresponding production list and passes after restoration.

## Verification

- Latest full suite, Python 3.14.9: **2,590 passed, 1 skipped**, in 71.75s. Command: `pytest tests/ -n 4 -m 'not slow' -q -o addopts= --cov=counter_risk.web_demo --cov-report=json:/tmp/issue-1219-fields-full.json --cov-report=term-missing`. See [field-full-suite.log](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/field-full-suite.log). This measures the specific tested module; it makes no claim about current overall coverage.
- Targeted command: `pytest tests/test_web_demo_helpers.py tests/test_web_demo_smoke.py -m 'not slow' -q -o addopts= --cov=counter_risk.web_demo --cov-report=term-missing`: **46 passed, 1 deselected**, `web_demo.py` **100% (127/127 statements)**. See [field-targeted.log](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/field-targeted.log).
- Prior focused/adjacent suites: **353 passed, 14 deselected**, with eight explicit module coverage options; see [targeted.log](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/targeted.log).
- Ruff passes with CI flags: `ruff check --output-format github --extend-exclude .workflows-lib .`. `git diff --check` passes. Black 26.10.1 formats the changed Python test file and the required repository-wide command `black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .` passes for **403 files**. The existing serial driver warmed a temporary writable cache after the native parallel runner stalled; the unmodified native command then passed with `BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/issue-1219-field-black-cache`. See [field-black.log](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/field-black.log) and [field-validation.json](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/field-validation.json).
- Published head `4176a42` has passing [Gate](https://github.com/stranske/Counter_Risk/actions/runs/40845116004) and [Agents Guard](https://github.com/stranske/Counter_Risk/actions/runs/40845115733) runs. These include both previous production fixes. Hosted checks for the new 25-case test expansion require publication.

## Real break-and-revert proof

All **56 added test functions / 112 unique parameter cases** have actual mutation proof:

- [Original receipts](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/mutation-receipts.json): 53 functions / 76 cases. Each mutation fails with exit 1; its restored run passes with exit 0. MOSERS checks include seeded stale-row clearing, section boundaries, and complete missing-sheet diagnostics.
- [Runtime-transition receipts](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/followup-mutation-receipts.json): one function / two cases, with four mutations and restored passing runs.
- [Symlink receipts](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/symlink-mutation-receipts.json): one function / three cases, with four mutations and restored passing runs.
- [Relocation receipts](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/relocation-mutation-receipts.json) and [transcript](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/relocation-mutation-transcript.txt): one function / four cases. All four cases first failed against the original production code. Deliberately normalizing only fallback paths causes **4 failures**; separately omitting cash, screenshot, or discovery paths causes **1 corresponding failure each**. Each restored run passes. Source bytes match their original SHA-256 after every experiment.

- [Exposure-summary receipts](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/exposure-mutation-receipts.json) and [transcript](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/exposure-mutation-transcript.txt): two additional parameter cases in the existing relocation and symlink tests. Both fail on the original source ([before log](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/exposure-before.log)). After fixing them, independently remove each of the two new production lines: its matching test fails with exit 1, and passes with exit 0 after restoration. Source SHA-256 is verified after both experiments.

- [Complete source-field matrix receipts](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/field-mutation-receipts.json): **25 additional parameter cases**, comprising 12 relocation cases and 13 fixture-containment cases. Remove only the matching field from the production relocation set or fixture-source map; its selected test fails with exit 1. Restore the original bytes, verify SHA-256, and rerun that same test; it passes with exit 0. Each JUnit report contains exactly one case. All 25 experiments completed successfully, with no production changes retained.

## Coverage and partial delivery

Local whole-suite counts use the same source configuration and `-m 'not slow'`. The pre-follow-up baseline excludes the eight PR-added test modules and measures **68.9506%** overall line coverage. The previous candidate measured **90.7744%**; the relocation fix measures **90.7819%** overall and additionally covers all ten newly introduced production statements. The overall difference is dominated by unrelated module coverage and is sensitive to import/collection order; it must not be attributed wholesale to this PR. See [baseline.log](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/baseline.log), [coverage-summary.json](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/coverage-summary.json), and the latest relocation validation receipt.

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

Only **5 fewer missed target lines** are measured locally, **175 short** of approximately 180. The relocation and exposure-summary follow-ups fix behavior and add **zero reductions in existing missed lines**. The latest targeted and whole-suite runs both measure `web_demo.py` at 127/127 covered statements (100%); no other target's metric was remeasured in the latest run. The 25-case expansion preserves that 100% result and adds zero reductions in existing missed lines. CI blended coverage reduction remains unverified.

Remaining paths: `repo_cash_sources.py:192` handles `None` from `csv.DictReader`, which normal iteration does not yield; `limits.py:211` checks an empty validated limit list despite schema validation requiring entries; `data_quality.py:494` is a category fallback already handled by the code-to-category mapping; `context.py:16-22` covers alternate optional-PyArrow import shapes absent locally. The other four targets have no missed lines in the local whole-suite run. No fake runtime states, source refactors, exclusions, or threshold changes were introduced to force those defensive paths into the metric. The above-90 local measurement includes existing PR tests and is not a pre-initiative CI baseline.

## Reconciled tasks

Reviewed commits `3096e73`, `1942913`, `6d64651`, `67929e5`, `fe3ec4c`, `ab0eaac`, and `4176a42` and their test, full-suite, and mutation evidence. The five nested contract checkboxes were stale; the evidence supports checking them:

1. [x] Pick the next target by the repo's own coverage-gap ranking (escaped-defect priority, then churn, then uncovered mass), not by file size. The issue explicitly ranks all eight targets; work starts with `web_demo.py`.
2. [x] Every new test must FAIL when the code it covers is deliberately broken and PASS when reverted. Receipts above record actual failing and restored passing runs for every added case.
3. [x] Real bugs found while writing tests get fixed with a minimal, targeted diff in the same PR, not worked around. Both relocation and exposure-summary regressions fail on the original code, pass with scoped fixes, and the full non-slow suite passes.
4. [x] Low blast radius only: target tests and two targeted production fixes in `web_demo.py`, without refactors.
5. [x] One PR per logical chunk of work: existing PR #1221.

- [x] Disclose the authoritative CI baseline, differing local metric, partial shortfall, and remaining target paths.
- [x] Verify prior symlink tests/evidence are published at `fe3ec4c` and its hosted Gate and Agents Guard pass.
- [x] Publish the relocation fix and regression tests: published at `ab0eaac`.
- [ ] Publish the reconciled PR body: the metadata update requires approval unavailable in this run.
- [x] Verify hosted checks for the relocation fix at `ab0eaac`: Gate and Agents Guard pass.
- [x] Fix the exposure-summary relocation and fixture-validation omissions and verify both new cases with break-and-revert, targeted coverage, and the full non-slow suite.
- [x] Publish the exposure-summary fix and regression cases: live PR head is `4176a42`.
- [x] Verify hosted checks for the exposure-summary fix: Gate and Agents Guard pass at `4176a42`.
- [x] Expand the first-ranked target's fixture-field regressions and verify all 25 new cases by individual break-and-revert, focused coverage, and the full non-slow suite.
- [ ] Publish the new 25-case test expansion.
- [ ] Verify hosted checks for the test expansion.

## Publication status

PR #1221 is open and ready for review (`draft=false`) at `4176a42`, verified in this run. Its existing Gate and Agents Guard runs pass. Its live body still describes only the first two targets; this file is the reconciled replacement. The primary checkout has read-only Git metadata, so the verified test changes are committed in `/tmp/issue-1219-field-commit`. The GitHub connector rejected the PR-body update, requested `needs-human` label, and blocker comment with `MCP tool call requires approval, but approval policy is never`. No remote metadata changed. The push of the verified test commit to the existing PR branch failed with `Could not resolve host: github.com` (exit 128). The final commit is preserved in that writable checkout and in the portable bundle `/tmp/issue-1219-fields.bundle`. Final read-only verification confirms PR #1221 remains open, `draft=false`, at `4176a42`; publication of the 25 new cases is not claimed. No new hosted verification is claimed before the test expansion is published.

Closes #1219
