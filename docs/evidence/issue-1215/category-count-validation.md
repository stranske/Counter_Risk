# Later-category count validation

The issue's ranking puts `pipeline/manifest_schema.py` first. The existing branch
already covers all eight ranked modules; this follow-up keeps the same PR and
adds two public validation/write cases for the first target. A valid first
category must not hide a negative or boolean count in a later category under
`data_quality.counts.by_category`. The diagnostic must name the category and
field, and a rejected write must preserve both valid existing output files.
No production bug was found and no production change was made.

## Actual break-and-revert results

| Source mutation | Broken | Restored |
| --- | --- | --- |
| Remove the minimum constraint | Negative-count case: 1 failed | 2 passed |
| Accept booleans as integers | Boolean-count case: 1 failed | 2 passed |
| Skip schema-object map validation | 2 failed | 2 passed |

Every new collected case failed at an assertion under a real source mutation;
collection and fixture errors were not accepted as witnesses. Source bytes were
restored exactly. See [category-count-mutations.json](category-count-mutations.json)
and [category-count-mutation-transcript.txt](category-count-mutation-transcript.txt).

## Validation

- Baseline focused schema module: **81 passed**, **100% lines and branches**.
- Candidate schema and conformance suite: **88 passed**, **100% lines and
  branches** (149 statements, 100 branches). Command:
  `pytest -q tests/pipeline/test_manifest_schema.py tests/pipeline/test_manifest_schema_conformance.py -m 'not slow' --cov=counter_risk.pipeline.manifest_schema --cov-branch --cov-report=term-missing`.
- Whole non-slow suite: **2637 passed, 1 skipped**, 145.16 seconds. The eight
  targets have **1757 statements, 13 missing, 99% line coverage**. Results are in
  [category-count-suite-transcript.txt](category-count-suite-transcript.txt).
- The original missing-line reduction remains **177**, three short of the
  180-unit aim. The two new cases add no coverage gain. This targeted measurement
  does not establish a repository-wide percentage. The issue/Gate baseline
  remains authoritative.
- Black formatted the changed file with line length 100. Both repository-wide
  Black CLI checks below passed: **401 files unchanged**. Repository-wide Ruff
  with CI flags, `git diff --check`, and `git diff --exit-code -- src` passed.

```sh
black --line-length 100 tests/pipeline/test_manifest_schema.py
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/1215-category-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/1215-category-black-cache black --check --line-length 100 --exclude '(\.venv|\.workflows-lib|node_modules)' .
ruff check --output-format github --extend-exclude .workflows-lib .
git diff --check
git diff --exit-code -- src
```

The first uncached Black CLI attempt stalled and was interrupted (exit 130).
A sequential check using Black's `get_sources` and `reformat_one` APIs verified
all 401 files and populated its normal cache. Both direct CLI commands then
passed. No cache entries were fabricated and no formatter configuration changed.

## Delivery

The supplied checkout's Git metadata is read-only (`.git/index.lock` cannot be
created). Implementation and verification ran in a writable local clone at
`/tmp/counter-risk-1215-followup`, based on PR head `8b42d63`. The replacement PR
description is [pr-body.md](pr-body.md). Publication status is recorded there.

The PR-description/title update was rejected with `MCP tool call requires
approval, but approval policy is never`. No alternate API was used to bypass
this rejection. Therefore the five checked contract items in `pr-body.md` are
verified local evidence; the live PR's stale description/checkboxes remain
unchanged.

The follow-up was committed in the writable clone. Push to the existing PR
branch failed with `Could not resolve host: github.com`. The blocker-comment
and `needs-human` label requests were also rejected by the approval policy.
PR #1216 was rechecked after validation: open, `draft=false`, remote head
`8b42d63`. The replacement PR description has not been applied. Matching
files were copied back to the supplied workspace for the automation handoff;
its read-only Git metadata prevents recording the commit there. A Git bundle
and format-patch are retained under `/tmp` for publishing the local commit.
