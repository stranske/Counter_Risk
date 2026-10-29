## Summary

Strengthen the MOSERS regression tests so an unused row starts with stale data, clearing must remove it, and writes preserve cells before/after the section and outside mapped columns. Verify the generator reports both missing required sheets and name the existing closure test accurately. These changes address assertions that could previously pass without proving the intended behavior.

Reconciled commits `3096e73` and `1942913`: the PR already adds eight test files covering all eight issue-ranked targets, in the prescribed order. The earlier PR description mentioning only two targets was stale. Production code is unchanged; no real production bug was demonstrated.

## Verification

- Full local suite, Python 3.14.9: **2,554 passed, 1 skipped**, `pytest tests/ -n 4 -m 'not slow' -q -o addopts= --cov=counter_risk --cov-report=json:/tmp/1221-final.json --cov-report=term`, 94.63s. Coverage source is the unchanged project configuration.
- Focused and adjacent suites: **353 passed, 14 deselected**, with the eight explicit module `--cov` options and `--cov-report=term-missing`; see [targeted.log](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/targeted.log).
- Every added parameter case has an actual break-and-revert run: **53 test functions / 76 parameter cases** failed under corresponding behavior mutations (exit 1, assertion failures rather than collection errors), then passed with source bytes restored (exit 0). [Receipts](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/mutation-receipts.json) contain each named case, exact text mutation, command, failure names, return codes and restored source SHA-256; [transcript](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/mutation-transcript.txt) contains the outputs. All final source hashes match the restored hashes. The strengthened stale-row test fails when clearing is replaced with `pass`; the missing-sheet test fails when the diagnostic retains only the first missing name.
- Black 26.10.1: all **403 Python files** pass the required line-length/exclusion check. Default CLI worker startup raises sandbox `PermissionError` binding the multiprocessing forkserver socket. The successful run uses the same Black CLI discovery/configuration and `--check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .`, substituting serial calls to Black's own `reformat_one` for its multiprocessing scheduler. No formatting rules, exclusions or failures are suppressed. The changed file also passes the ordinary single-file Black command. [Black result](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/black.log).
- Repository CI Ruff command passes: `ruff check --output-format github --extend-exclude .workflows-lib .`. `git diff --check` passes.
- Existing hosted head `1942913` has passing [Gate](https://github.com/stranske/Counter_Risk/actions/runs/40836183192) and Agents Guard statuses. The follow-up changes have **not** been published or tested in hosted CI.

## Coverage and partial delivery

The issue's **89.32% blended coverage / 185 missing ranked units** remains the authoritative CI baseline. Current `pyproject.toml` explicitly sets `branch=false`; all local measurements here are line-only and cannot establish that CI blended delta.

The baseline excludes all eight PR-added test files, uses the same source configuration and `-m 'not slow'`, and passes **2,478 tests, 1 skipped** in 96.85s. Its overall coverage is **68.9506%** versus the final candidate's **90.7744%**. The change is dominated by unrelated module coverage and is sensitive to import/collection order; it must not be attributed wholesale to these tests. See [baseline.log](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/baseline.log), [candidate.log](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/candidate.log), and [per-file summaries](https://github.com/stranske/Counter_Risk/blob/codex/issue-1219/docs/evidence/issue-1219/coverage-summary.json).

The whole-suite target counts are:

| Target, in issue order | Baseline missed lines | Candidate missed lines | Candidate line coverage |
| --- | ---: | ---: | ---: |
| `web_demo.py` | 0 | 0 | 100.00% |
| `mosers/workbook_generation.py` | 0 | 0 | 100.00% |
| `parsers/repo_cash_sources.py` | 1 | 1 | 99.44% |
| `compute/limits.py` | 1 | 1 | 99.46% |
| `pipeline/data_quality.py` | 6 | 1 | 99.62% |
| `chat/context.py` | 4 | 4 | 97.04% |
| `chat/session.py` | 0 | 0 | 100.00% |
| `demo_artifact.py` | 0 | 0 | 100.00% |

Only **5 fewer missed target lines** are measured locally: **175 short** of the requested approximately 180. Hosted CI coverage reduction is unverified. This is a partial PR with concrete test quality improvements, not a claim that focused coverage added 185 CI units.

Remaining paths: `repo_cash_sources.py:192` handles `None` from `csv.DictReader`, which normal iteration does not yield; `limits.py:211` checks an empty validated limit list even though the schema requires entries; `data_quality.py:494` is a category fallback already handled by the code-to-category mapping; `context.py:16-22` covers alternate optional-PyArrow import shapes not present locally. The other four targets have no local whole-suite missed lines. No source edits, fake runtime states, refactors, thresholds or exclusions were added to force those defensive paths into the metric.

## Publication blocker

PR #1221 was reverified **open, draft=false**, on head `1942913`. The GitHub connector rejects the PR-body update with `MCP tool call requires approval, but approval policy is never`. The checkout's `.git` is read-only: `git add` cannot create `.git/index.lock`. A portable commit/bundle is prepared in a writable temporary repository; the primary checkout and remote PR cannot be advanced by this run. This file is the reviewable replacement PR body, with reconciled checkboxes below, awaiting publication.

Closes #1219

## Reconciled tasks and acceptance

- [x] Use CI's baseline as authoritative and explicitly disclose the local metric/baseline difference.
- [x] Run repository formatter and linter flags on all changed/added files; disclose the serial Black execution workaround.
- [ ] Publish all verified changes and update this live PR body; blocked by write approval and read-only Git metadata.
- [ ] Current follow-up passes hosted CI; local full suite and every-test mutation proof are complete, but this follow-up is unpublished.
- [x] State the partial coverage shortfall and explain remaining target paths.
- [x] Production changes only for demonstrated bugs: no production code changes in this PR.
- [x] Follow the issue's prescribed ranking.
- [x] Run and record real break-and-revert proof for every added test case.
- [x] Review possible bugs without working around any demonstrated defect; no real production bug was found.
- [x] Keep the change focused: tests/evidence only, no refactors.
- [x] Keep one PR for this logical chunk.
- [ ] Hosted coverage acceptance remains unverified; the local above-90 result is after the PR's tests, not a verified pre-start CI baseline.
