# Nested configuration snapshot regression

Reviewed the recent commits through `eb4d039` before adding this follow-up.
Their recorded coverage and mutation evidence supports checking all five
contract subtasks: target ranking, actual break-and-revert, minimal bug fixes,
low blast radius, and one PR. The reconciled replacement description remains
in [pr-body.md](pr-body.md). The live description update, blocker comment, and
`needs-human` label were each rejected with `MCP tool call requires approval,
but approval policy is never`. No alternate API bypass was attempted.

The first ranked target, `manifest_schema.py`, already has verified 100% line
and branch coverage. The next target, `manifest.py`, has two remaining legacy
conversion statements after JSON-mode serialization has already converted the
values. A synthetic configuration would be needed to execute those statements.
Instead, this regression protects the public nested-path serialization contract
with a real validated `WorkflowConfig`, followed by manifest writing and JSON
reading. Nested screenshot paths, the output root, and the date survive; the
caller's configuration retains its Path and date values. No production change
was needed. This test adds no coverage gain.

## Verified results

- Replacing `config.model_dump(mode="json")` with `config.model_dump()` caused
  the new test to fail at its nested snapshot assertion: **1 failed**.
- Restoring source bytes exactly gave **1 passed**. Mutation command, change,
  source hash, and both outputs are recorded in
  [config-snapshot-mutation.json](config-snapshot-mutation.json) and
  [config-snapshot-mutation-transcript.txt](config-snapshot-mutation-transcript.txt).
- Focused module: **28 passed**, `manifest.py` **92%** line coverage in isolation.
- Whole non-slow suite: **2638 passed, 1 skipped**, 151.00 seconds. Across all
  eight targets: **1757 statements, 13 missing, 99%** line coverage. `manifest.py`
  remains at **99%**, missing lines 450 and 452. See the focused and suite
  transcripts and [coverage comparison](config-snapshot-coverage-comparison.json).
- The original-gap reduction remains **177 lines**, three short of the
  180-unit aim. Current CI configuration measures lines, whereas the issue's
  89.32% baseline describes blended line and branch coverage. Use Gate's baseline
  for acceptance; this does not establish a repository-wide percentage.
- Black formatted the changed test with line length 100. Both required and CI
  repository-wide Black commands below passed: **401 files unchanged**. Ruff,
  whitespace checks, and the production-source comparison passed.

```sh
black --line-length 100 tests/pipeline/test_manifest.py
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/1215-snapshot-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/1215-snapshot-black-cache black --check --line-length 100 --exclude '(\.venv|\.workflows-lib|node_modules)' .
ruff check --output-format github --extend-exclude .workflows-lib .
git diff --check
git diff --exit-code -- src
```

Uncached Black CLI attempts stalled and were interrupted (exit 130). Sequential
Black `get_sources` / `reformat_one` checks verified every file. The genuine
cache from that run was moved to Black's versioned cache directory, then both
exact CLI checks passed. No cache entries or formatter settings were fabricated.

The supplied checkout has read-only Git metadata. Implementation and validation
used `/tmp/counter-risk-1215-snapshot`, a local clone based on `eb4d039`, for
committing the verified test and evidence. The existing PR remains #1216;
the checked contract items in the prepared description are local reconciliation,
not a claim that the rejected remote edits succeeded.

The verified test and evidence were committed in that writable clone. Push to
`origin HEAD:codex/issue-1215` failed with `Could not resolve host: github.com`.
PR #1216 was rechecked open with `draft=false`, still at remote head `eb4d039`.
A Git bundle and format-patch are retained in `/tmp` for publication, and the
committed files are copied back to the supplied checkout for automation handoff.
