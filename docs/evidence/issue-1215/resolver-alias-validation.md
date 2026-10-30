# Resolver alias regression validation

Reviewed commits `297f840`, `4eefcbe`, and `bdf0a05` before continuing.
The existing coverage comparisons and mutation receipts support completing all
five contract subtasks in the PR's automated checklist. The prepared description
at [pr-body.md](pr-body.md) retains those completed checkboxes. The live PR body
update was rejected by automatic approval review: `MCP tool call requires
approval, but approval policy is never`. No alternate write API was attempted.

Issue #1215's first-ranked target, `pipeline/manifest_schema.py`, was rechecked:
**92 passed, 149 statements, 100 branches, 0 missing or partial, 100% coverage**.
The earlier evidence explains the remaining public-contract gaps in the other
targets. This follow-up adds two regression cases for the recent resolver fix
in ranked target five, `pipeline/reconciliation.py`. No production changes or
additional covered original lines are claimed.

The cases exercise both warning and strict policies with two raw aliases that
resolve to one canonical name. They require original whitespace in exception
metadata, all aliases in warning metadata, and reuse of the first resolution
pass when assembling raw metadata. The resolver would return a changed name on
subsequent calls, so an accidental second pass cannot silently pass.

## Actual break-and-revert

| Deliberate source change | Broken | Restored |
| --- | --- | --- |
| Stop passing previously resolved canonical names into metadata construction | 2 failed at assertions | 2 passed |
| Strip raw label spacing when adding metadata | 2 failed at assertions | 2 passed |

Both cases failed under both mutations and passed after restoration. The
production source was restored byte for byte after every mutation; collection
or fixture errors were not counted. See [mutation receipts](resolver-alias-mutations.json)
and [actual transcript](resolver-alias-mutation-transcript.txt).

## Validation

- Focused reconciliation/boundary/manifest suite: **83 passed**, 96% line and
  branch coverage for reconciliation (194 statements, 88 branches). This focused
  percentage does not replace the whole-suite or original Gate measurement.
- Whole non-slow suite: **2644 passed, 1 skipped**, 87 deselected, 191.67 seconds.
  The eight ranked targets have **1761 statements, 14 missing, 99%** line coverage.
  Original-gap reduction remains **176 lines**, **four short of the 180-unit aim**.
  The original 89.32% blended CI baseline remains authoritative; this local,
  line-only result does not establish repository-wide 90% or hosted Gate results.
- Black formatted the changed test with line length 100. Both required and CI
  repository-wide Black checks exited 0: **401 files unchanged**. Ruff with CI
  flags, whitespace checks, and the unchanged-production-source check passed.
- The initial Black process reported 401 unchanged files but timed out at
  shutdown (exit 124). Both subsequent exact CLI checks exited 0; the timed-out
  attempt was not counted as a successful check.

Receipts: [whole suite](resolver-alias-suite-transcript.txt),
[focused suite](resolver-alias-focused-transcript.txt),
[schema coverage](resolver-alias-schema-transcript.txt),
[coverage comparison](resolver-alias-coverage-comparison.json),
[format/lint](resolver-alias-lint-transcript.txt).

## Delivery constraints

The supplied checkout has read-only Git metadata. Work is committed in the
writable local clone `/tmp/counter-risk-1215-resolver`, based on `297f840`, and
the resulting files are copied into the supplied checkout for automation handoff.
PR #1216 was verified open and ready (`draft=false`) before the rejected update.
No second PR was created.

Source/test and evidence commit: `596e4c3`. Publication with
`git push origin HEAD:codex/issue-1215` failed because this sandbox could not
resolve `github.com`. The verified work is committed locally but was not
published by this run. A Git bundle and format-patch are retained at
`/tmp/1215-resolver-alias.bundle` and `/tmp/1215-resolver-alias.patch` for recovery.
The committed files are copied back to the supplied checkout for the automation
handoff. Hosted checks for this new commit remain unverified.

The blocker comment and `needs-human` label were also rejected by automatic
approval review with the same approval-policy reason. None of the three remote
write attempts changed PR metadata. Final read-only verification still showed
PR #1216 open with `draft=false` at `297f840`.
