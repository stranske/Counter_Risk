# Later-exposure confidence validation

Reviewed commits through `fb5b9de` and their committed coverage and mutation
evidence before implementation. All five numbered contract subtasks are
verified in the prepared [PR body](pr-body.md). The live description is stale.
The connector rejected the description update, explanatory comment, and
`needs-human` label with `MCP tool call requires approval, but approval policy
is never`. No alternate API bypass was attempted.

The first-ranked target is `pipeline/manifest_schema.py`. Its existing tests
reject invalid confidence in the first exposure, but do not protect traversal
to a later exposure. The new test starts with confidence 0 and 1 in two
independent exposure records and writes valid outputs. It then changes only
the second confidence to 2, checks the diagnostic names array index 1, and
verifies the invalid write preserves both existing files. No production bug
was found and no production source change was needed.

## Verification

- Actual mutation: replace `for index, item in enumerate(value):` with
  `for index, item in enumerate(value[:1]):`. The new test failed at its
  validation assertion (**1 failed**); byte-for-byte restoration gave
  **1 passed**. The [mutation record](later-exposure-mutation.json) contains
  the command and restored source hash; the [transcript](later-exposure-mutation-transcript.txt)
  records both outputs.
- Focused schema and conformance tests: **89 passed**. Coverage table shows
  `manifest_schema.py`: **149 statements, 0 missing, 100 branches, 0 partial,
  100% coverage**. Command:
  `pytest tests/pipeline/test_manifest_schema.py tests/pipeline/test_manifest_schema_conformance.py -m 'not slow' --cov=counter_risk.pipeline.manifest_schema --cov-branch --cov-report=term-missing -q`.
- Whole non-slow suite: **2639 passed, 1 skipped**, 79.63 seconds. Coverage
  across all eight ranked targets: **1757 statements, 13 missing, 99%**.
  See [full output](later-exposure-suite-transcript.txt) and
  [coverage comparison](later-exposure-coverage-comparison.json).
- Every target's statement count and missing-line set match the preceding
  measurement. The original-gap reduction remains **177 lines**, three short
  of 180. This test adds no line-coverage gain. Current configuration measures
  lines; the issue's blended CI baseline remains authoritative.
- Black formatted the changed Python file with line length 100. Both required
  and CI repository-wide Black checks passed (**401 files unchanged**).
  Repository-wide Ruff with CI flags, whitespace checks, and production-source
  comparison passed. Exact commands and output: [lint transcript](later-exposure-lint-transcript.txt).
- The initial uncached Black CLI run stalled and was interrupted (exit 130).
  Black's `get_sources` and `reformat_one` then checked every source sequentially
  and populated genuine cache entries using the same mode. Both exact CLI
  checks subsequently passed; no formatter settings or cache results were fabricated.

## Delivery

The supplied checkout's Git metadata is read-only. Work and verification use
the local writable clone `/tmp/counter-risk-1215-array`, based on `fb5b9de`.
The checked task items in the prepared description are local reconciliation,
not a claim that the rejected live update succeeded.

The test and evidence were committed in that writable clone. Push to the
existing branch, `git push origin HEAD:codex/issue-1215`, failed with
`Could not resolve host: github.com`. PR #1216 was rechecked open with
`draft=false`, still at head `fb5b9de`. The committed files are copied back to
the supplied checkout for automation handoff; a Git bundle and format-patch
are retained at `/tmp/1215-later-exposure.bundle` and
`/tmp/1215-later-exposure.patch`. Live checkbox reconciliation and publication
remain blocked by the tool approval policy and network access, respectively.
