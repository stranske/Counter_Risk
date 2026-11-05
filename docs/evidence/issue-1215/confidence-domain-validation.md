# Confidence domain contract follow-up

Reviewed recent commits `ba3969a`, `4af5ae2`, `c80d63c`, `e186f35`, and
`277e56d` before continuing. Their evidence supports checking all five remaining
contract items. The reconciled description is in [pr-body.md](pr-body.md).
The live PR update was rejected, so remote checkboxes remain unchanged.

The first-ranked target, `pipeline/manifest_schema.py`, was already at 100%
line and branch coverage in the baseline focused suite (79 passed). This
follow-up adds five public validation/write cases: the smallest negative float,
a negative integer, a large negative integer, and both booleans are invalid
confidence values. Each failed write must preserve the bytes of a valid prior
manifest and summary. No production bug or production change was needed.

## Real mutation verification

- Remove the numeric minimum check: three negative cases failed, two boolean
  cases passed. Restore the source: all five passed.
- Remove the number type's boolean exclusion: both boolean cases failed, three
  negative cases passed. Restore the source: all five passed.
- Every new collected case failed under a deliberate mutation. XML assertions
  checked failures rather than collection/fixture errors. Source restoration was
  byte-for-byte verified. See [confidence-domain-mutations.json](confidence-domain-mutations.json)
  and [confidence-domain-mutation-transcript.txt](confidence-domain-mutation-transcript.txt).

## Validation

- Focused schema and conformance suite: **84 passed**, schema **100%** lines and
  branches (149 statements, 100 branches). Exact command and output are in
  [confidence-domain-coverage-transcript.txt](confidence-domain-coverage-transcript.txt).
- Every non-slow test together, with coverage targeted to the eight issue
  modules: **2633 passed, 1 skipped** in 110.23 seconds. Targets have 1757
  statements and 13 missing lines. See [confidence-domain-suite-transcript.txt](confidence-domain-suite-transcript.txt).
- Original gap reduction remains **177 lines**, three short of the aim of 180.
  The new cases add no metric gain. The issue/Gate baseline remains authoritative;
  this targeted table does not establish repository-wide coverage.
- `black --line-length 100 tests/pipeline/test_manifest_schema.py`: passed.
- Both required repository-wide Black commands passed, **401 files unchanged**:

```sh
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/1215-domain-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/1215-domain-black-cache black --check --line-length 100 --exclude '(\.venv|\.workflows-lib|node_modules)' .
ruff check --output-format github --extend-exclude .workflows-lib .
git diff --check
```

The initial uncached Black command stalled and was interrupted (exit 130).
A sequential check using Black's `get_sources` and `reformat_one` APIs checked
all 401 files with the repository settings and populated its ordinary cache in
`/tmp`. Both direct CLI commands then exited 0. No cache values were fabricated,
and no formatter settings were changed. Ruff and the whitespace check passed.

## Publication blockers

`git add` failed with `Unable to create .../.git/index.lock: Read-only file system`.
These five tests and their evidence remain uncommitted and unpushed. The previous
upper-bound fix is already committed at `277e56d`.

The authorized PR reconciliation update was rejected with
`MCP tool call requires approval, but approval policy is never`. No alternate
API was used. The concrete replacement description remains local.

PR #1216 was checked after validation: open, `draft=false`, head `277e56d`.
No CI result is claimed for the new uncommitted tests.
