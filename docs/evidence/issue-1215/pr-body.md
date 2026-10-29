## Summary

Add boundary tests for the eight targets in issue #1215's specified order. This follow-up adds four manifest persistence tests covering source-date conflict evidence, explicit PPT statuses, disabled PPT output, and a skipped distribution deck when only the master exists. No production changes or real bugs were found.

Reconciliation: reviewed `ba3969a` and `4af5ae2`. They changed eight unique test files (the schema file changed in both commits), covering all eight ranked targets. The previous PR description incorrectly said seven targets were untouched. The verification below includes those earlier tests.

## Coverage and remaining work

Measured with every non-slow test together, targeting these eight modules with `--cov`. The current repository configuration measures lines (`branch=false`), whereas the issue describes its 89.32% repository baseline as blended coverage. These results do not establish a new repository-wide percentage or replace Gate's figures.

| Ranked target | Base missing lines | Candidate missing lines | Base coverage | Candidate coverage |
| --- | ---: | ---: | ---: | ---: |
| pipeline/manifest_schema.py | 14 | 0 | 90% | 100% |
| pipeline/manifest.py | 21 | 2 | 93% | 99% |
| writers/historical_update.py | 36 | 6 | 90% | 98% |
| parsers/cprs_fcm.py | 23 | 2 | 90% | 99% |
| pipeline/reconciliation.py | 21 | 0 | 89% | 100% |
| observability/langsmith_fleet.py | 15 | 0 | 92% | 100% |
| name_registry.py | 8 | 3 | 92% | 97% |
| parsers/cprs_ch.py | 52 | 1 | 80% | 99% |

Local gain: **176 covered lines**, with 14 remaining, **four short of the 180-unit aim**. The local base has 190 missing lines; the issue lists 188 units, with manifest.py accounting for the two-unit difference (local 21, issue 19). Use the issue/Gate baseline for CI acceptance; no 180-unit CI gain is claimed.

Remaining paths:

- `manifest.py:450,452`: legacy Path/date conversion after `model_dump(mode="json")` already converts those values. Faking the serializer would not exercise a real configuration path.
- `historical_update.py:126,208,212,271,621,789`: default-root discovery, name-resolution and worksheet compatibility fallbacks, and defensive blank-date checks after a last-dated-row scan. These remain follow-up work; this PR does not claim they are all dead code.
- `cprs_fcm.py:162,176`: the totals marker also supplies the header words, and the section locator stops before the futures marker. The new real-workbook tests exercise the reachable neighboring errors without patching these helpers into inconsistent states.
- `name_registry.py:50,63,98`: typed Pydantic validation rejects these input types before the field validators run. Directly calling the validators would bypass the public validation path.
- `cprs_ch.py:273`: a defensive column-completion path; parsed records already contain the output fields, including the empty-frame case.

The focused manifest suite additionally improved from **95% to 99% line-plus-branch coverage** (147 tests before, 151 after). This focused improvement is not an additional whole-suite gain. Focused schema coverage is **100% lines and branches**.

## Actual break-and-revert evidence

Every one of the **144 newly added parametrized cases** was run against a real source mutation and failed, then passed with the original source restored. Collection/fixture errors were not counted as evidence. No assertions were weakened.

The audit applied one condition inversion, bypassed raise, or dropped return value at a time, ran the remaining selected node IDs, restored the source, and reran all new cases in each module. Five additional direct mutations verify the new manifest behaviors and the previously unproven empty-SHA cases:

| Source mutation | Red result | Reverted result |
| --- | --- | --- |
| Replace date-conflict details with an empty object | 1 failed | 1 passed |
| Ignore explicit PPT overrides and infer success from files | 1 failed | 1 passed |
| Bypass the disabled-PPT guard | 1 failed | 1 passed |
| Report the absent distribution deck as successful | 1 failed | 1 passed |
| Return an empty SHA string instead of None | 2 failed, 1 passed | 3 passed |

Exact mutations, failed node IDs, and green reruns are recorded in [mutation-results.json](mutation-results.json), [manifest-contract-mutations.json](manifest-contract-mutations.json), and [mutation-transcript.txt](mutation-transcript.txt). Whole-suite coverage counts and commands are in [coverage-comparison.json](coverage-comparison.json).

## Validation

- Base revision `faad152`, clean snapshot: **2478 passed, 1 skipped**.
- Candidate snapshot (`4af5ae2` plus the four new manifest tests): **2622 passed, 1 skipped**.
- Both whole-suite commands used `pytest tests/ -n 2 -m "not slow"` and targeted `--cov` options for the eight modules; source snapshots matched the delivered source after mutation reverts.
- Focused manifest coverage: **151 passed**, 99% line-plus-branch coverage.
- Focused schema coverage: **70 passed**, 100% line-plus-branch coverage.
- Formatter/linter and final workspace checks are recorded in [validation.md](validation.md).

## Reconciled contract tasks

- [x] Pick targets by issue #1215's coverage-gap ranking, rather than file size.
- [x] Run break-and-revert proof for every new case and record both results.
- [x] Fix any real bugs minimally: none found; production files unchanged.
- [x] Keep the blast radius low: tests and verification evidence only, no refactors.
- [x] Keep one PR for this chunk: #1216, open and ready for review.

Local validation is complete; CI for the additional four tests must still run. The existing head `4af5ae2` has a successful Gate run. Coverage remains a partial delivery with the shortfall and remaining paths stated above.

Closes #1215
