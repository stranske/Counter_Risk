## Summary

Add boundary tests for the eight targets in issue #1215's specified order. Manifest persistence tests cover source-date conflict evidence, explicit PPT statuses, disabled PPT output, and a skipped distribution deck when only the master exists. Two additional cases verify that default workbook discovery uses the module's repository root, even when the current directory contains a valid decoy workbook, for both preferred and legacy directories. No production changes or real bugs were found.

Reconciliation: reviewed `ba3969a`, `4af5ae2`, and `c80d63c`. They changed eight unique test files (some in multiple commits), covering all eight ranked targets. The live PR description incorrectly says seven targets were untouched and leaves the five contract checkboxes unchecked. The verified contract checkboxes below reconcile those commits. Applying this replacement description was rejected because the tool requires approval and this run's approval policy is `never`.

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

Local gain: **177 covered lines**, with 13 remaining, **three short of the 180-unit aim**. The local base has 190 missing lines; the issue lists 188 units, with manifest.py accounting for the two-unit difference (local 21, issue 19). Use the issue/Gate baseline for CI acceptance; no 180-unit CI gain is claimed.

Remaining paths:

- `manifest.py:450,452`: legacy Path/date conversion after `model_dump(mode="json")` already converts those values. Faking the serializer would not exercise a real configuration path.
- `historical_update.py:208,212,271,621,789`: name-resolution fallbacks require a result without a canonical key, while current resolvers always supply one. Current openpyxl worksheet types use the preceding dictionary or iterator paths rather than the final cell-access compatibility fallback. Blank-date guards run after a scan has already found a dated row. Testing these paths would require synthetic compatibility objects or inconsistent scan results; this PR leaves them unchanged rather than claiming coverage through those arrangements. Default-root discovery is now covered through the public workbook-opening function.
- `cprs_fcm.py:162,176`: the totals marker also supplies the header words, and the section locator stops before the futures marker. The new real-workbook tests exercise the reachable neighboring errors without patching these helpers into inconsistent states.
- `name_registry.py:50,63,98`: typed Pydantic validation rejects these input types before the field validators run. Directly calling the validators would bypass the public validation path.
- `cprs_ch.py:273`: a defensive column-completion path; parsed records already contain the output fields, including the empty-frame case.

The focused manifest suite additionally improved from **95% to 99% line-plus-branch coverage** (147 tests before, 151 after). This focused improvement is not an additional whole-suite gain. Focused schema coverage is **100% lines and branches**.

## Actual break-and-revert evidence

Every one of the **146 newly added parametrized cases** was run against a real source mutation and failed, then passed with the original source restored. Collection/fixture errors were not counted as evidence. No assertions were weakened.

The audit applied one condition inversion, bypassed raise, or dropped return value at a time, ran the remaining selected node IDs, restored the source, and reran all new cases in each module. Five additional direct mutations verify the new manifest behaviors and the previously unproven empty-SHA cases:

| Source mutation | Red result | Reverted result |
| --- | --- | --- |
| Replace date-conflict details with an empty object | 1 failed | 1 passed |
| Ignore explicit PPT overrides and infer success from files | 1 failed | 1 passed |
| Bypass the disabled-PPT guard | 1 failed | 1 passed |
| Report the absent distribution deck as successful | 1 failed | 1 passed |
| Return an empty SHA string instead of None | 2 failed, 1 passed | 3 passed |
| Discover the workbook root using `Path.cwd()` | 2 failed at the selected workbook path assertion | 2 passed |

Exact mutations, failed node IDs, and green reruns are recorded in [mutation-results.json](mutation-results.json), [manifest-contract-mutations.json](manifest-contract-mutations.json), [mutation-transcript.txt](mutation-transcript.txt), and [root-discovery-mutation-transcript.txt](root-discovery-mutation-transcript.txt). Whole-suite coverage counts and commands are in [coverage-comparison.json](coverage-comparison.json) and [root-discovery-coverage-comparison.json](root-discovery-coverage-comparison.json).

## Validation

- Base revision `faad152`, clean snapshot: **2478 passed, 1 skipped**.
- Previous candidate snapshot (`4af5ae2` plus the four new manifest tests): **2622 passed, 1 skipped**.
- Current workspace (`c80d63c` plus the two root-discovery cases): **2624 passed, 1 skipped**.
- All whole-suite commands used `pytest tests/ -n 2 -m "not slow"` and targeted `--cov` options for the eight modules; source snapshots matched the delivered source after mutation reverts.
- Focused manifest coverage: **151 passed**, 99% line-plus-branch coverage.
- Focused schema coverage: **70 passed**, 100% line-plus-branch coverage.
- New historical boundary suite: **29 passed**. Whole-suite targeted coverage for `historical_update.py`: **99%**, 5 of 360 lines missed (previously 6).
- Repository-wide Black checks with both required exclude patterns: **401 files unchanged**. Repository-wide Ruff with CI flags and `git diff --check`: passed.
- Earlier formatter/linter results are recorded in [validation.md](validation.md); this follow-up is recorded in [root-discovery-validation.md](root-discovery-validation.md).

## Reconciled contract tasks

- [x] Pick targets by issue #1215's coverage-gap ranking, rather than file size.
- [x] Run break-and-revert proof for every new case and record both results.
- [x] Fix any real bugs minimally: none found; production files unchanged.
- [x] Keep the blast radius low: tests and verification evidence only, no refactors.
- [x] Keep one PR for this chunk: #1216, open and ready for review.

Local validation is complete. The existing head `c80d63c` has a successful Gate run (40834166290); CI for the two new cases must still run. This run cannot commit or push because `.git/index.lock` cannot be created on the read-only Git directory. The PR-body update was separately rejected by tool approval policy, so this description and the new tests remain local. Coverage remains a partial delivery with the shortfall and remaining paths stated above.

Closes #1215
