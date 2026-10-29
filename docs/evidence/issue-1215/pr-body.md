## Summary

Expand regression coverage across all eight targets in issue #1215's specified
ranking. Tests cover manifest validation and persistence, workbook discovery and
preservation, parsers, reconciliation, observability, and name validation. Keep
this chunk in PR #1216.

Tests exposed two real bugs, fixed with narrow production changes:

- Enforce the schema's existing confidence maximum of 1 before writing outputs.
- Propagate the custom reconciliation resolver when constructing raw metadata,
  preserving original counterparty labels such as CIBC when canonical names change.
  The strengthened regression failed against the original code and all 62 focused
  reconciliation/boundary/manifest tests passed after the fix (commit `bdf0a05`).

The latest follow-up adds three evidence row cases in the first-ranked target.
Null and row 1 round-trip; zero, booleans, and fractional rows are rejected with
a precise diagnostic while both saved output files remain intact. No production
change or line-coverage gain was needed for this follow-up.

## Coverage and shortfall

Measured with every non-slow test together and coverage targeted to these eight modules. Current repository configuration measures lines (`branch=false`); the issue's 89.32% baseline describes blended line and branch coverage. These measurements do not establish a repository-wide percentage or replace Gate's figures.

| Ranked target | Base missing lines | Candidate missing lines | Base coverage | Candidate coverage |
| --- | ---: | ---: | ---: | ---: |
| pipeline/manifest_schema.py | 14 | 0 | 90% | 100% |
| pipeline/manifest.py | 21 | 2 | 93% | 99% |
| writers/historical_update.py | 36 | 5 | 90% | 99% |
| parsers/cprs_fcm.py | 23 | 2 | 90% | 99% |
| pipeline/reconciliation.py | 21 | 1 | 89% | 99% |
| observability/langsmith_fleet.py | 15 | 0 | 92% | 100% |
| name_registry.py | 8 | 3 | 92% | 97% |
| parsers/cprs_ch.py | 52 | 1 | 80% | 99% |

Local reduction: **176 previously missing lines covered**, **four short of the 180-unit aim**. Base `faad152` has 190 missing lines in these targets versus the issue's 188 units; `manifest.py` accounts for the two-unit difference (21 locally versus 19 in the issue). Use the issue/Gate baseline for acceptance; no 180-unit CI gain is claimed. The production fixes add six statements, excluded from the original-gap reduction. The corrected reconciliation resolver makes the previously covered defensive empty-exception fallback unreachable through these public inputs; the latest count includes that uncovered original statement.

Remaining paths cannot be meaningfully covered through the current public contracts:

- `manifest.py:450,452`: legacy Path/date conversion after Pydantic JSON-mode serialization already converts those types.
- `historical_update.py:208,212,271,621,789`: name-resolution fallbacks require absent canonical keys, unlike current resolvers; cell-access fallback requires a worksheet without the dictionary or iterator interface supplied by openpyxl; blank-date guards follow a scan that already found a dated row. Synthetic compatibility objects or inconsistent scan results would be needed. Public default-root workbook discovery is covered.
- `reconciliation.py:329`: strict-mode empty-exception fallback. The corrected resolver keeps canonical and raw metadata aligned, so a missing canonical name supplies an original raw name and raises the populated exception instead.
- `cprs_fcm.py:162,176`: totals markers also supply header words, and section discovery stops before the futures marker; reachable neighboring failures are covered with real workbooks.
- `name_registry.py:50,63,98`: Pydantic rejects these types before field validators run.
- `cprs_ch.py:273`: parsed records already supply the output fields, including empty frames.

Counts and commands: [coverage comparison](https://github.com/stranske/Counter_Risk/blob/codex/issue-1215/docs/evidence/issue-1215/evidence-row-coverage-comparison.json).

## Actual break-and-revert proof

Prior evidence covers 161 collected cases added earlier in this PR. The three
latest cases each failed at assertions when their evidence row constraint was
weakened, and each passed after byte-for-byte source restoration:

| Row schema mutation | Broken | Restored |
| --- | --- | --- |
| Lower row minimum from 1 to 0 | zero-row: 1 failed | 1 passed |
| Allow boolean rows | boolean-row: 1 failed | 1 passed |
| Allow fractional number rows | fractional-row: 1 failed | 1 passed |

Exact commands, failed assertions, and source hashes:
[evidence-row-mutations.json](https://github.com/stranske/Counter_Risk/blob/codex/issue-1215/docs/evidence/issue-1215/evidence-row-mutations.json),
[actual transcript](https://github.com/stranske/Counter_Risk/blob/codex/issue-1215/docs/evidence/issue-1215/evidence-row-mutation-transcript.txt).
Earlier proof remains in `mutation-results.json`, `manifest-contract-mutations.json`,
`root-discovery-mutation.json`, `confidence-mutations.json`,
`confidence-domain-mutations.json`, `action-validation-mutations.json`,
`category-count-mutations.json`, `config-snapshot-mutation.json`, and
`later-exposure-mutation.json` in the same evidence directory.

## Validation

- Whole non-slow suite: **2642 passed, 1 skipped**, 87 deselected, 210.61 seconds. Eight targets: **1761 statements, 14 missing, 99%** line coverage. The original-gap reduction is **176 lines**, **four short of 180**; this follow-up adds no line-coverage gain.
- Focused schema/conformance suite: **92 passed**, `manifest_schema.py` **100% lines
  and branches** (149 statements, 100 branches, 0 missing or partial).
- Required and CI repository-wide Black checks passed (**401 files unchanged**).
  Ruff with CI flags and whitespace checks passed. Production source is unchanged
  from `4eefcbe` in this follow-up.
- These are local results. Hosted checks at the delivered head remain authoritative.
  [Validation and delivery notes](https://github.com/stranske/Counter_Risk/blob/codex/issue-1215/docs/evidence/issue-1215/evidence-row-validation.md).

## Verified contract tasks

- [x] Pick targets by issue #1215's coverage-gap ranking, rather than file size.
- [x] Run actual break-and-revert for every added case and retain both results.
- [x] Fix real bugs minimally: confidence bounds and original counterparty labels.
- [x] Keep the blast radius low: focused tests and two narrow fixes, no refactors.
- [x] Keep one PR for this chunk: #1216, open and ready for review (`draft=false`).

Coverage remains a disclosed partial delivery. No repository-wide 90% claim is made.

Closes #1215
