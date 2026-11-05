# Evidence row validation

Issue #1215 ranks `pipeline/manifest_schema.py` first (14 original uncovered
units, churn 8). Prior rounds already verified 100% lines and branches there;
this follow-up protects the public evidence row contract without claiming an
additional coverage gain. No production change was needed.

The three new cases accept and persist both null (unknown row) and row 1,
then reject row 0, boolean True, or fractional row 1.5 with an exact diagnostic.
Each invalid write must preserve the saved manifest and data-quality summary.

## Actual break-and-revert

Each collected case was run with a deliberately changed evidence row schema:
minimum 0 for `zero-row`, adding boolean to the allowed types for `boolean-row`,
and replacing integer with number for `fractional-row`. Each mutated run
failed at its validation assertion (1 failed), and each restored run passed
(1 passed). The production source was restored byte-for-byte after every
mutation. No collection errors were counted. See
[evidence-row-mutations.json](evidence-row-mutations.json) and
[evidence-row-mutation-transcript.txt](evidence-row-mutation-transcript.txt).

## Verification

- Baseline focused suite: 89 passed, 100% lines and branches.
- Updated focused suite: 92 passed, 149 statements, 0 missing, 100 branches,
  0 partial, 100% coverage. Command:
  `pytest tests/pipeline/test_manifest_schema.py tests/pipeline/test_manifest_schema_conformance.py -m 'not slow' --cov=counter_risk.pipeline.manifest_schema --cov-branch --cov-report=term-missing -q`.
- Whole non-slow suite: **2642 passed, 1 skipped**, 87 deselected, 210.61 seconds. Eight targets: **1761 statements, 14 missing, 99%** line coverage. The original-gap reduction is **176 lines**, **four short of 180**; this follow-up adds no line-coverage gain.
- Black formatted the changed test with line length 100. The required
  repository-wide Black check and CI's Black check both passed (401 files
  unchanged). Ruff with CI flags and `git diff --check` passed. Production
  source matches head `4eefcbe` exactly.
- The initial uncached Black CLI stalled and was interrupted (exit 130).
  Sequential Black `get_sources` / `reformat_one` checked every file using
  the configured target and line length and populated Black's genuine cache.
  Both exact CLI checks then passed; no cache results were fabricated.

Transcripts: [focused coverage](evidence-row-coverage-transcript.txt),
[whole suite](evidence-row-suite-transcript.txt), [lint](evidence-row-lint-transcript.txt).

## Delivery

The supplied checkout has read-only Git metadata. Work and verification use
`/tmp/counter-risk-1215-evidence-row`, a writable local clone of `4eefcbe`.
The test and evidence are committed there and copied back for automation
handoff. This local evidence does not establish hosted CI results.

The PR title/body update, blocker comment, and `needs-human` label were each
rejected by automatic approval review: `MCP tool call requires approval, but
approval policy is never`. The prepared description reconciles the five
verified contract tasks, but the live checkboxes were not changed. No alternate
API bypass was attempted. PR #1216 was verified open with `draft=false` at
head `4eefcbe` before the publication attempt.

Source/test and evidence commit: `56ba61b`. Publishing to the GitHub origin with
`git push origin HEAD:codex/issue-1215` failed because this environment could
not resolve `github.com`. The verified work is therefore committed locally,
but is not published by this run. A follow-up documentation commit records
this blocker. A Git bundle and format-patch are retained at
`/tmp/1215-evidence-row.bundle` and `/tmp/1215-evidence-row.patch`; the committed
files are copied to the supplied checkout for the automation handoff.
