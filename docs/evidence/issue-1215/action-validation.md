# Recommended-action validation follow-up

Reviewed all six PR commits through `d06892d` before continuing. Their coverage,
mutation evidence, and the minimal confidence-maximum fix support completing the
five contract checkboxes. The replacement description in [pr-body.md](pr-body.md)
now reflects those commits. The live PR update was rejected, so remote task
checkboxes remain unchanged.

The first-ranked target already had 100% focused line and branch coverage.
Two new cases strengthen its public recommended-action validator: a valid first
action must not hide whitespace-only category/action fields in the second action.
The diagnostics must identify index 1 and the failing field. Valid `warn` and
`fail` actions are checked before introducing the invalid field. No production
bug was found and no production change was needed.

## Actual break-and-revert results

| Deliberate source mutation | Broken | Restored |
| --- | --- | --- |
| Remove category whitespace stripping | 1 failed | 1 passed |
| Remove action whitespace stripping | 1 failed | 1 passed |
| Validate only the first action | 2 failed | 2 passed |

Every new collected case failed at an assertion under a real source mutation and
passed after restoration. Source bytes were restored and their SHA-256 recorded
in [action-validation-mutations.json](action-validation-mutations.json). Exact
commands and output are in [action-validation-mutation-transcript.txt](action-validation-mutation-transcript.txt).

## Verification

- Before: focused schema and conformance suite **84 passed**, 100% lines and branches.
- After: **86 passed**, schema **100%** (149 statements, 100 branches).
  See [action-validation-coverage-transcript.txt](action-validation-coverage-transcript.txt).
- Whole non-slow suite with coverage targeted to the eight ranked modules:
  **2635 passed, 1 skipped** in 128.25 seconds. Targets have 1757 statements,
  13 missing, 99% coverage. See [action-validation-suite-transcript.txt](action-validation-suite-transcript.txt).
- The original gap reduction remains **177 lines**, three short of the aim.
  These two cases add no line-coverage gain. CI/Gate remains authoritative.
- Black formatted the changed test file at line length 100. Both repository-wide
  commands below passed: **401 files unchanged**. Ruff, whitespace checks, and
  byte-for-byte production-source comparison with HEAD passed.

```sh
black --line-length 100 tests/pipeline/test_manifest_schema.py
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/1215-actions-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/1215-actions-black-cache black --check --line-length 100 --exclude '(\.venv|\.workflows-lib|node_modules)' .
ruff check --output-format github --extend-exclude .workflows-lib .
git diff --check
git diff --exit-code -- src
```

Uncached Black CLI attempts stalled and were interrupted (exit 130). Black's
sequential `get_sources`/`reformat_one` checks verified all 401 files with the
repository settings and populated its ordinary cache. The first sequential
check used a cache directory without the version suffix; a second check used
Black's default versioned cache. Both direct CLI checks then passed. No cache
values were fabricated or formatter settings changed.

## Publication blockers

`git add tests/pipeline/test_manifest_schema.py` failed with exit 128 because
`.git/index.lock` cannot be created on the read-only Git directory. The two new
cases and this run's evidence remain uncommitted and unpushed.

The PR-description update, the blocker comment, and the `needs-human` label were
all rejected with `MCP tool call requires approval, but approval policy is never`.
No alternate API was used to bypass those rejections. Apply the verified changes
from a writable checkout and use [pr-body.md](pr-body.md) to reconcile the PR.

PR #1216 was verified open and ready for review (`draft=false`), head `d06892d`.
No new remote CI result is claimed for these two local cases.
