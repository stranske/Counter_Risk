## Summary

Add boundary tests for all eight targets in issue #1215's specified ranking. Previous commits cover manifest persistence, historical workbook discovery and preservation, parser boundaries, reconciliation, observability, and name validation.

The first ranked target also had a real contract bug: `_EVIDENCE_SCHEMA` declares confidence `maximum: 1`, but `_check_node` did not enforce maximum bounds. Three new regression cases prove that values immediately above 1, integer 2, and a large integer were accepted. The minimal production fix enforces numeric maximum bounds alongside the existing minimum check. A fourth case verifies JSON round-trips for null, both bounds, and an interior value. Invalid writes preserve existing manifest and summary bytes. No refactors or unrelated production changes.

Reconciliation: reviewed `ba3969a`, `4af5ae2`, `c80d63c`, and `e186f35`. They cover all eight ranked targets, despite the old PR description saying only the first target was touched. The verified contract checkboxes below reflect the accumulated work and this regression fix.

## Coverage and remaining work

Measured with every non-slow test together, targeting these eight modules with `--cov`. The current repository configuration measures lines (`branch=false`), whereas the issue describes its 89.32% repository baseline as blended coverage. These results do not establish a new repository-wide percentage or replace Gate's figures.

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

Local reduction: **177 previously missing lines covered**, with 13 remaining, **three short of the 180-unit aim**. The local base has 190 missing lines; the issue lists 188 units, with manifest.py accounting for the two-unit difference (local 21, issue 19). Use the issue/Gate baseline for CI acceptance; no 180-unit CI gain is claimed.

Remaining paths:

- `manifest.py:450,452`: legacy Path/date conversion after `model_dump(mode="json")` already converts those values. Faking the serializer would not exercise a real configuration path.
- `historical_update.py:208,212,271,621,789`: name-resolution fallbacks require a result without a canonical key, while current resolvers always supply one. Current openpyxl worksheet types use the preceding dictionary or iterator paths rather than the final cell-access compatibility fallback. Blank-date guards run after a scan has already found a dated row. Testing these paths would require synthetic compatibility objects or inconsistent scan results; this PR leaves them unchanged rather than claiming coverage through those arrangements. Default-root discovery is now covered through the public workbook-opening function.
- `cprs_fcm.py:162,176`: the totals marker also supplies the header words, and the section locator stops before the futures marker. The new real-workbook tests exercise the reachable neighboring errors without patching these helpers into inconsistent states.
- `name_registry.py:50,63,98`: typed Pydantic validation rejects these input types before the field validators run. Directly calling the validators would bypass the public validation path.
- `cprs_ch.py:273`: a defensive column-completion path; parsed records already contain the output fields, including the empty-frame case.

The focused manifest suite additionally improved from **95% to 99% line-plus-branch coverage** (147 tests before, 151 after). This focused improvement is not an additional whole-suite gain. Focused schema coverage is **100% lines and branches**.

The upper-bound fix adds two covered statements. Those new statements do not reduce the original gap, so the reported gain remains 177. The current whole-suite run covers all 149 statements in `manifest_schema.py`; its focused line-plus-branch coverage is 100% (149 statements, 100 branches).

## Actual break-and-revert evidence

Every one of the **150 newly added collected cases** was run against a real source mutation and failed, then passed with the original source restored. Collection/fixture errors were not counted as evidence. No assertions were weakened.

The audit applied one condition inversion, bypassed raise, or dropped return value at a time, ran the remaining selected node IDs, restored the source, and reran all new cases in each module. Additional direct mutations verify the new manifest behaviors and the previously unproven empty-SHA cases:

| Source mutation | Red result | Reverted result |
| --- | --- | --- |
| Replace date-conflict details with an empty object | 1 failed | 1 passed |
| Ignore explicit PPT overrides and infer success from files | 1 failed | 1 passed |
| Bypass the disabled-PPT guard | 1 failed | 1 passed |
| Report the absent distribution deck as successful | 1 failed | 1 passed |
| Return an empty SHA string instead of None | 2 failed, 1 passed | 3 passed |
| Remove the confidence maximum check | 3 failed, 1 passed | 4 passed |
| Make the maximum exclusive (`>` to `>=`) | 1 failed | 4 passed |
| Discover the workbook root using `Path.cwd()` | 2 failed at the selected workbook path assertion | 2 passed |

Exact mutations, failed node IDs, and green reruns are recorded in [mutation-results.json](mutation-results.json), [manifest-contract-mutations.json](manifest-contract-mutations.json), [mutation-transcript.txt](mutation-transcript.txt), and [root-discovery-mutation-transcript.txt](root-discovery-mutation-transcript.txt). Whole-suite coverage counts and commands are in [coverage-comparison.json](coverage-comparison.json) and [root-discovery-coverage-comparison.json](root-discovery-coverage-comparison.json).

The confidence regression first failed against the original implementation (3 failed, 1 passed). The four new cases reject values above 1 without overwriting either output file and round-trip `None`, `0`, `0.5`, and `1`. Exact failing assertions, green reruns, and the restored source hash are in [confidence-mutation-transcript.txt](confidence-mutation-transcript.txt) and [confidence-mutations.json](confidence-mutations.json).

## Validation

- Base revision `faad152`, clean snapshot: **2478 passed, 1 skipped**.
- Earlier candidate `e186f35`: **2624 passed, 1 skipped**, as recorded in the root-discovery evidence.
- Current workspace with the upper-bound fix and four new cases: **2628 passed, 1 skipped**, using every non-slow test together and targeted coverage for the eight issue modules. The table shows **1757 statements, 13 missing, 99%** across those targets; this is not repository-wide coverage. Command and output: [confidence-coverage-transcript.txt](confidence-coverage-transcript.txt). Comparison: [confidence-coverage-comparison.json](confidence-coverage-comparison.json).
- Schema and conformance tests before this fix: **75 passed**. After the fix: **79 passed**, **100% line-plus-branch coverage** for `manifest_schema.py`.
- Every one of the four new collected cases fails under a deliberate source mutation and passes after restoration. The fixed source was restored byte-for-byte.
- Both changed Python files were formatted with Black at line length 100. Required and CI repository-wide Black checks: **401 files unchanged**. Repository-wide Ruff with CI flags, targeted mypy for the production module, and `git diff --check`: passed.
- Full details: [confidence-validation.md](confidence-validation.md). Earlier mutation and coverage evidence remains in this directory.

## Reconciled contract tasks

- [x] Pick targets by issue #1215's coverage-gap ranking, rather than file size.
- [x] Run break-and-revert proof for every new case and record both results.
- [x] Fix real bugs minimally: enforce the already-declared confidence maximum, with failing-before and passing-after regression evidence.
- [x] Keep the blast radius low: boundary tests and one targeted schema-validator fix, no refactors.
- [x] Keep one PR for this chunk: #1216, verified open and ready for review (`isDraft=false`).

Coverage remains a partial delivery: 177 original missing lines covered, three short of the 180-unit aim. Each remaining path is explained above; the issue/Gate baseline remains authoritative. The newly verified upper-bound fix and tests are local: this run cannot stage a commit because `.git/index.lock` cannot be created on the read-only Git directory. No commit, push, or CI result for the new changes is claimed.

The authorized description update was separately rejected with `MCP tool call requires approval, but approval policy is never`. This replacement description remains local; no alternate API was used to bypass the rejection.

Closes #1215
