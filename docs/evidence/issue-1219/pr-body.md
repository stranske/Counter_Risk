## Summary

Add discriminating tests for all eight issue-ranked targets in the prescribed order. A follow-up found and fixes a real bug in the first-ranked target, `web_demo.py`: relocating a demo configuration to accommodate a repository-fixture fallback changed the base directory for its other relative inputs. Valid fixture configurations consequently failed validation or passed incorrect paths to the pipeline. Resolve every configured fixture source against the original configuration before writing its relocated copy, including optional cash, raw inputs, screenshots, and discovery roots. The original YAML remains unchanged. No refactor or unrelated production change is included.

This is a partial coverage delivery. The issue's **89.32% blended CI baseline / 185 missing ranked units** remains authoritative. Current configuration uses line-only coverage (`branch=false`); local results cannot establish the requested CI blended reduction.

## Verification

- Latest full suite, Python 3.14.9: **2,563 passed, 1 skipped**, in 129.92s. Command: `pytest tests/ -n 4 -m 'not slow' -q -o addopts= --cov=counter_risk --cov-report=json:/tmp/issue-1219-relocation-full.json --cov-report=term`. See [relocation-full-suite.log](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/relocation-full-suite.log).
- Targeted command: `pytest tests/test_web_demo_helpers.py tests/test_web_demo_smoke.py -m 'not slow' -q -o addopts= --cov=counter_risk.web_demo --cov-report=term-missing`: **19 passed, 1 deselected**, `web_demo.py` **100% (127/127 statements)**. See [relocation-targeted.log](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/relocation-targeted.log).
- Prior focused/adjacent suites: **353 passed, 14 deselected**, with eight explicit module coverage options; see [targeted.log](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/targeted.log).
- Ruff passes with CI flags: `ruff check --output-format github --extend-exclude .workflows-lib .`. `git diff --check` passes. Black 26.10.1 passes for both changed Python files through its native CLI. The repository-wide check passes for **403 files**, preserving the required `--check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .` flags and substituting only a serial scheduler. Default multiprocessing cannot bind a forkserver socket in this sandbox; thread/fork scheduler attempts were interrupted. The [driver](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/relocation-black-driver.txt) and [output](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/relocation-black.log) make the successful check reproducible. `mypy src/counter_risk/web_demo.py` passes.
- Published head `fe3ec4c` has passing [Gate](https://github.com/stranske/Counter_Risk/actions/runs/40841522434) and [Agents Guard](https://github.com/stranske/Counter_Risk/actions/runs/40841521908) statuses. These cover the previous symlink follow-up. Hosted checks for this relocation fix are pending publication.

## Real break-and-revert proof

All **56 added test functions / 85 unique parameter cases** have actual mutation proof:

- [Original receipts](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/mutation-receipts.json): 53 functions / 76 cases. Each mutation fails with exit 1; its restored run passes with exit 0. MOSERS checks include seeded stale-row clearing, section boundaries, and complete missing-sheet diagnostics.
- [Runtime-transition receipts](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/followup-mutation-receipts.json): one function / two cases, with four mutations and restored passing runs.
- [Symlink receipts](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/symlink-mutation-receipts.json): one function / three cases, with four mutations and restored passing runs.
- [Relocation receipts](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/relocation-mutation-receipts.json) and [transcript](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/relocation-mutation-transcript.txt): one function / four cases. All four cases first failed against the original production code. Deliberately normalizing only fallback paths causes **4 failures**; separately omitting cash, screenshot, or discovery paths causes **1 corresponding failure each**. Each restored run passes. Source bytes match their original SHA-256 after every experiment.

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

Only **5 fewer missed target lines** are measured locally, **175 short** of approximately 180. This follow-up fixes behavior and adds **zero reductions in existing missed lines**. CI blended coverage reduction remains unverified.

Remaining paths: `repo_cash_sources.py:192` handles `None` from `csv.DictReader`, which normal iteration does not yield; `limits.py:211` checks an empty validated limit list despite schema validation requiring entries; `data_quality.py:494` is a category fallback already handled by the code-to-category mapping; `context.py:16-22` covers alternate optional-PyArrow import shapes absent locally. The other four targets have no missed lines in the local whole-suite run. No fake runtime states, source refactors, exclusions, or threshold changes were introduced to force those defensive paths into the metric. The above-90 local measurement includes existing PR tests and is not a pre-initiative CI baseline.

## Reconciled tasks

Reviewed commits `3096e73`, `1942913`, `6d64651`, `67929e5`, and `fe3ec4c` and their test, full-suite, and mutation evidence. The five nested contract checkboxes were stale; the evidence supports checking them:

1. [x] Pick the next target by the repo's own coverage-gap ranking (escaped-defect priority, then churn, then uncovered mass), not by file size. The issue explicitly ranks all eight targets; work starts with `web_demo.py`.
2. [x] Every new test must FAIL when the code it covers is deliberately broken and PASS when reverted. Receipts above record actual failing and restored passing runs for every added case.
3. [x] Real bugs found while writing tests get fixed with a minimal, targeted diff in the same PR, not worked around. The relocation regression fails on the original code, passes with the scoped fix, and the full non-slow suite passes.
4. [x] Low blast radius only: target tests and one targeted production fix, without refactors.
5. [x] One PR per logical chunk of work: existing PR #1221.

- [x] Disclose the authoritative CI baseline, differing local metric, partial shortfall, and remaining target paths.
- [x] Verify prior symlink tests/evidence are published at `fe3ec4c` and its hosted Gate and Agents Guard pass.
- [ ] Publish the relocation fix, regression tests, and reconciled PR body.
- [ ] Verify hosted checks for the relocation fix.

## Publication blocker

The existing PR is open and ready for review (`draft=false`) at `fe3ec4c`. Its live body still describes only the first two targets. This file is the reconciled replacement body. The GitHub PR-body update returned `MCP tool call requires approval, but approval policy is never`; no remote metadata was changed. The primary checkout cannot create `.git/index.lock` because its Git metadata is read-only. A writable local checkout and portable commit bundle preserve the verified fix; publication remains blocked by the current execution permissions.

Closes #1219
