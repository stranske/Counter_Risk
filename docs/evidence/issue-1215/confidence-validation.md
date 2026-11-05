# Confidence upper-bound regression

The first target in issue #1215's ranking is `pipeline/manifest_schema.py`.
Earlier commits already covered its missing lines, but a contract audit found
that `_EVIDENCE_SCHEMA` declares `maximum: 1` for confidence while `_check_node`
never enforces `maximum`. The public validator accepted confidence values of
`1.0000000000000002`, `2`, and `10**400`.

Four new collected cases exercise the public validator and manifest writer.
Three reject the out-of-range values and verify that both existing output files
retain their bytes after the rejected write. The fourth round-trips confidence
values `None`, `0`, `0.5`, and `1` through JSON persistence. The production change
adds a numeric upper-bound check matching the existing lower-bound check; no
schema, threshold, exclusion, dependency, or unrelated production code changes.

## Verified regression and mutation checks

- Existing schema and conformance tests before edits: **75 passed**, schema
  **100% line and branch coverage** (147 statements, 98 branches).
- New cases against the original implementation: **3 failed, 1 passed**. Each
  rejection case failed because `validate_manifest` returned `(True, None)`.
- Fixed schema and conformance tests: **79 passed**, schema **100% line and
  branch coverage** (149 statements, 100 branches).
- Remove the actual new maximum check: **3 failed, 1 passed**. Restore the fixed
  source: **4 passed**.
- Change `value > maximum` to `value >= maximum`: the valid-boundary case
  **fails**. Restore the fixed source: **4 passed**.
- All four new cases have a real failing mutation and a passing restored run.
  Source restoration is byte-for-byte verified. Commands, results, and source
  hash are in [confidence-mutations.json](confidence-mutations.json); assertion
  failures and green output are in
  [confidence-mutation-transcript.txt](confidence-mutation-transcript.txt).

The focused coverage command was:

```sh
pytest tests/pipeline/test_manifest_schema.py tests/pipeline/test_manifest_schema_conformance.py --cov=counter_risk.pipeline.manifest_schema --cov-branch --cov-report=term-missing -m 'not slow' -q
```

## Formatting and lint

The complete non-slow suite passed: **2628 passed, 1 skipped**, in 114.79 seconds.
Coverage targeted all eight issue modules while running every test file together:
**1757 statements, 13 missing, 99%** across the targets. This is a reduction of
177 missing original lines from `faad152`, three short of the 180-unit aim.
The fix adds two covered production statements, which are not counted as a
reduction in the original gap. The current CI configuration measures lines;
the issue/Gate baseline remains authoritative. Exact command and table are in
[confidence-coverage-transcript.txt](confidence-coverage-transcript.txt); counts
and remaining lines are in
[confidence-coverage-comparison.json](confidence-coverage-comparison.json).

`mypy src/counter_risk/pipeline/manifest_schema.py` passed with no issues found.

Both changed Python files were individually formatted with Black, line length
100, and were unchanged. The first two-file invocation failed because Black's
worker process could not bind a local socket in the sandbox. A sequential check
through Black's normal `reformat_one` API populated its ordinary cache and
reported **401 unchanged, 0 changed, 0 failed**. The following direct commands
then exited 0:

```sh
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/1215-confidence-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/1215-confidence-black-cache black --check --line-length 100 --exclude '(\.venv|\.workflows-lib|node_modules)' .
ruff check --output-format github --extend-exclude .workflows-lib .
git diff --check
```

Both direct Black checks reported **401 files would be left unchanged**. No
formatter settings or security restrictions were changed.

## Publication

After the formatting gate passed, staging the production fix, tests, and mutation
evidence failed:

```text
fatal: Unable to create '/home/runner/work/Counter_Risk/Counter_Risk/.git/index.lock': Read-only file system
```

The Git directory is read-only in this run. The verified changes remain in the
workspace; no commit or push is claimed.

The authorized PR-description update was also rejected:

```text
MCP tool call requires approval, but approval policy is never
```

No alternate API was used to bypass the rejection. The concrete replacement
description, corrected contract checkboxes, coverage shortfall, and bug explanation
are saved in [pr-body.md](pr-body.md). PR #1216 was verified open and ready for
review (`draft=false`) at `e186f358d7aa715212e30fbd8d326ed432989490`.
