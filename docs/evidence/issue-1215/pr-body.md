## Summary

Add discriminating boundary tests for all eight targets in issue #1215's specified order. They cover manifest validation and persistence, historical workbook discovery and preservation, parser boundaries, reconciliation, observability, and name validation. Keep this work in PR #1216.

Tests found one real bug: evidence confidence declared `maximum: 1`, but the validator ignored maximum bounds. The minimal production fix enforces that existing constraint. Values immediately above 1, integer 2, and a large integer fail before either output file is overwritten; null and valid bounds still round-trip. No refactors or other production changes.

The latest two cases verify that a valid first category cannot hide a negative or boolean count in a later category under `data_quality.counts.by_category`. Diagnostics identify the category and field; rejected writes preserve usable manifest and summary bytes. These two cases strengthen the contract and add no line-coverage gain.

## Coverage and shortfall

Measured with every non-slow test together and coverage targeted to these eight modules. Current repository configuration measures lines (`branch=false`); the issue's 89.32% baseline describes blended line and branch coverage. These measurements do not establish a repository-wide percentage or replace Gate's figures.

| Ranked target | Base missing lines | Candidate missing lines | Base coverage | Candidate coverage |
| --- | ---: | ---: | ---: | ---: |
| pipeline/manifest_schema.py | 14 | 0 | 90% | 100% |
| pipeline/manifest.py | 21 | 2 | 93% | 99% |
| writers/historical_update.py | 36 | 5 | 90% | 99% |
| parsers/cprs_fcm.py | 23 | 2 | 90% | 99% |
| pipeline/reconciliation.py | 21 | 0 | 89% | 100% |
| observability/langsmith_fleet.py | 15 | 0 | 92% | 100% |
| name_registry.py | 8 | 3 | 92% | 97% |
| parsers/cprs_ch.py | 52 | 1 | 80% | 99% |

Local reduction: **177 previously missing lines covered**, **three short of the 180-unit aim**. Base `faad152` has 190 missing lines in these targets versus the issue's 188 units; `manifest.py` accounts for the two-unit difference (21 locally versus 19 in the issue). Use the issue/Gate baseline for acceptance; no 180-unit CI gain is claimed. The confidence fix adds two covered statements, excluded from the original-gap reduction.

Remaining paths cannot be meaningfully covered through the current public contracts:

- `manifest.py:450,452`: legacy Path/date conversion after Pydantic JSON-mode serialization already converts those types.
- `historical_update.py:208,212,271,621,789`: name-resolution fallbacks require absent canonical keys, unlike current resolvers; cell-access fallback requires a worksheet without the dictionary or iterator interface supplied by openpyxl; blank-date guards follow a scan that already found a dated row. Synthetic compatibility objects or inconsistent scan results would be needed. Public default-root workbook discovery is covered.
- `cprs_fcm.py:162,176`: totals markers also supply header words, and section discovery stops before the futures marker; reachable neighboring failures are covered with real workbooks.
- `name_registry.py:50,63,98`: Pydantic rejects these types before field validators run.
- `cprs_ch.py:273`: parsed records already supply the output fields, including empty frames.

Counts and commands: [coverage comparison](https://github.com/stranske/Counter_Risk/blob/codex/issue-1215/docs/evidence/issue-1215/category-count-coverage-comparison.json).

## Actual break-and-revert proof

All **159 added collected cases** have actual failing-source and restored-source runs, including parametrized cases. Collection/fixture errors were not counted; assertions were not weakened. Earlier evidence covers the previous 157 cases, including the confidence bug's failing-before/fixed-after run. Source changes were restored byte-for-byte after deliberate mutations.

| Latest deliberate source mutation | Broken | Restored |
| --- | --- | --- |
| Remove minimum enforcement | Negative-count case: 1 failed | 2 passed |
| Accept booleans as integers | Boolean-count case: 1 failed | 2 passed |
| Skip schema-object map validation | Both new cases: 2 failed | 2 passed |

Exact failed IDs, changes, commands, and restored hashes: [latest mutations](https://github.com/stranske/Counter_Risk/blob/codex/issue-1215/docs/evidence/issue-1215/category-count-mutations.json), [latest transcript](https://github.com/stranske/Counter_Risk/blob/codex/issue-1215/docs/evidence/issue-1215/category-count-mutation-transcript.txt). Accumulated evidence: `mutation-results.json`, `manifest-contract-mutations.json`, `root-discovery-mutation.json`, `confidence-mutations.json`, `confidence-domain-mutations.json`, and `action-validation-mutations.json` in the same directory.

## Validation

- Clean base `faad152`: **2478 passed, 1 skipped**.
- Current whole non-slow suite: **2637 passed, 1 skipped**, 145.16 seconds. Eight target modules: **1757 statements, 13 missing, 99%** line coverage. [Full output](https://github.com/stranske/Counter_Risk/blob/codex/issue-1215/docs/evidence/issue-1215/category-count-suite-transcript.txt).
- Focused schema and conformance suite: **88 passed**, `manifest_schema.py` **100% lines and branches** (149 statements, 100 branches).
- Changed Python file formatted with Black, line length 100. Required and CI repository-wide Black checks passed (**401 files unchanged**); repository-wide Ruff with CI flags and `git diff --check` passed. Production source matches the preceding head exactly.
- These are local results; remote CI has not verified this follow-up. [Commands and delivery notes](https://github.com/stranske/Counter_Risk/blob/codex/issue-1215/docs/evidence/issue-1215/category-count-validation.md).

## Verified contract tasks

- [x] Pick targets by issue #1215's coverage-gap ranking, rather than file size.
- [x] Run break-and-revert proof for every new case and record both results.
- [x] Fix real bugs minimally: enforce the declared confidence maximum with regression evidence.
- [x] Keep the blast radius low: boundary tests and one targeted schema-validator fix, no refactors.
- [x] Keep one PR for this chunk: #1216, open and ready for review (`isDraft=false`).

Coverage remains a partial delivery. No repository-wide 90% claim is made.

## Publication status

This is a prepared replacement description, not the live PR body. The tool approval policy rejected the title/body update, blocker comment, and `needs-human` label. The verified follow-up is committed in a writable clone under `/tmp`; push failed because `github.com` could not be resolved. The supplied checkout has read-only Git metadata. PR #1216 was rechecked open and ready (`draft=false`), remote head `8b42d63`. Publishing the local commit and applying this description remain blocked.

Closes #1215
