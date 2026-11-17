<!-- bootstrap for codex on issue #1254 run:43990580121-1 -->

## Verified tasks

- [x] Combined task: parser provenance, historical warnings, data-quality findings, manifest sources, and regression assertions implemented and verified together.
- [x] Preserve `read_class_notional_breakdown(path) -> dict[str, float] | None`; add `ClassNotionalBreakdown` and the provenance reader.
- [x] Default the historical generator to the provenance reader; accept legacy mappings and missing results; warn for non-absolute Trend shares and invalid cells.
- [x] Warn when the merger uses record-derived shares; carry the chosen sources through historical output generation into the pipeline manifest.
- [x] Classify `CLASS_BREAKDOWN_FALLBACK` and `CLASS_BREAKDOWN_CELL_COERCED` as `warn` findings in `data_validation`.
- [x] Persist optional `class_breakdown_sources` and validate variant names and source values in the manifest schema.
- [x] Add parser, generator, merger, manifest, and data-quality regressions, including GREEN/YELLOW/RED and info/warn/fail precedence.
- [x] Additional task: named missing-Trend regression passes.
- [x] Additional task: deliberate break fails the named regression; reverting it restores the passing result.
- [x] Additional task: the entire historical-workbook test file passes.
- [x] Acceptance: named missing-Trend regression passes.
- [x] Acceptance: deliberate break and revert verified, with evidence below.
- [x] Acceptance: entire historical-workbook test file passes (24 tests).

## Deliberate break and revert

Temporarily changed `HistoricalWorkbookOutputGenerator.generate` to set Trend's
source to `absolute` regardless of the reader result, and skipped
`warn_class_breakdown` for Trend. This deliberately labels missing/plain data as
absolute and suppresses the fallback warning. The change was reverted before
the final verification and is absent from the final implementation.

Command used before the break, during the break, and after reverting:

```sh
python3 -m pytest tests/outputs/test_historical_workbook.py::test_trend_class_breakdown_missing_warns_record_derived_fallback -q -m 'not slow'
```

Before: **1 passed**. During the break: **1 failed**, exit status 1, with this
assertion diagnostic:

```text
AssertionError: {'warnings': [], 'overall_status': 'info', 'finding_codes': ['NO_FINDINGS'], 'trend_source': 'absolute'}
assert 0 == 1
```

After reverting: **1 passed**. The restored result records `record-derived` for
Trend, emits `CLASS_BREAKDOWN_FALLBACK` at severity `warn`, and writes a YELLOW
data-quality summary. The test reads the persisted manifest back from disk.

## Final validation

- `python3 -m pytest tests/outputs/test_historical_workbook.py -q -m 'not slow'`: **24 passed**.
- Parser, historical output, merger, data-quality, manifest, and pipeline regression files: **568 passed, 41 slow tests deselected**.
- Ruff on all changed Python files: **passed**.
- Mypy on the six changed source modules: **passed**.
- `git diff --check`: **passed**.
- Required Black gate: **422 files would be left unchanged**:

  ```sh
  BLACK_CACHE_DIR=/tmp/counter-risk-black-cache BLACK_NUM_WORKERS=1 black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
  ```

  Black's concurrent runner hung in this sandbox. Each of the 422 Python files
  was first checked successfully using Black's single-file CLI and its normal
  writable cache, then the whole-repository command above passed using that
  verified cache. No formatter rules or repository files were bypassed.

## Delivery blocker

The working tree contains the verified implementation, but committing is blocked
by the environment's read-only `.git` mount. Both `git add` and `git commit`
returned exit status 128:

```text
fatal: Unable to create '/home/runner/work/Counter_Risk/Counter_Risk/.git/index.lock': Read-only file system
```

No branch or pull request was created. A commit on the checked-out
`codex/issue-1254` branch remains necessary when Git metadata is writable.

## Follow-up verification (2026-11-17)

Added two parser regression cases for the first additional task: the selected
plain/absolute row reports exactly two invalid cells, excludes blanks and valid
zeros from that count, ignores damaged unused rows, and preserves the legacy
mapping result. These changes are in `tests/parsers/test_cprs_ch_boundaries.py`.

- [x] New parser cases verified; parser/output regressions: **63 passed**.
- [x] Named Trend fallback test: **1 passed** before the deliberate break,
  **1 failed** during it, and **1 passed** after restoring the source byte for byte.
  This time the temporary change set `source = "absolute"` whenever the variant
  was Trend and the chosen source was non-absolute. The failure again reported
  `warnings=[]`, `overall_status='info'`, `finding_codes=['NO_FINDINGS']`, and
  `trend_source='absolute'`. The temporary change is absent from the final code.
- [x] Whole historical-workbook file: **24 passed**.
- [x] Targeted parser, historical output, merger, data-quality, manifest, and
  pipeline regressions: **575 passed, 38 slow tests deselected** using
  `-m 'not slow'`.
- [x] Ruff on the changed Python file and `git diff --check`: **passed**.
- [x] All **422 Python files** passed Black's single-file CLI, then the required
  whole-repository Black command above passed with the verified writable cache.
- [ ] Commit the new parser cases on the checked-out `codex/issue-1254` branch.

The local commit attempt failed at `git add` with the same read-only
`.git/index.lock` error. A GitHub connector attempt to commit the tested file to
the existing PR branch was also rejected:

```text
MCP tool call requires approval, but approval policy is never
```

Updating PR #1255's verified checkboxes and recording this evidence in its body
was rejected for the same reason, as were attempts to add a blocker comment and
the `needs-human` label. Those remote checkboxes remain unchanged.
The new test cases and these notes remain in the working tree; committing them
requires writable Git metadata or an approved GitHub write capability.

## Reconciliation and parser structure regressions (2026-11-17)

Reviewed commits `3b450b5` and `ed6b875` and verified the six implementation
tasks against the current parser, generator, merger, data-quality, and manifest
code. Added missing-worksheet and malformed-worksheet-XML cases to
`test_class_breakdown_returns_none_when_unavailable`. Both use real XLSX
containers and verify that the provenance reader and legacy mapping reader
return `None`, preserving the contract that triggers record-derived warnings.

- [x] Parser and historical-workbook regressions: **53 passed**.
- [x] Named Trend fallback regression: **1 passed** before the deliberate
  break, **1 failed** with the break, **1 passed** after restoring the source
  byte for byte. The temporary defect forced non-absolute Trend sources to
  `absolute` before warning generation; the failure showed `warnings=[]`,
  `overall_status='info'`, `finding_codes=['NO_FINDINGS']`, and
  `trend_source='absolute'`. No temporary defect remains in the working tree.
- [x] Complete historical-workbook file: **24 passed**.
- [x] Other affected parser, data-quality, manifest-schema, merger, pipeline,
  and PPT-status regressions: **480 passed, 38 slow tests deselected**.
  All pytest commands used `-m 'not slow'`.
- [x] Ruff on the changed Python test file and `git diff --check`: **passed**.
- [x] Required whole-repository Black gate: **422 files would be left
  unchanged**, after verifying each file through Black's single-file CLI to
  populate the writable cache used by the command documented above.
- [ ] Commit the new parser structure cases on `codex/issue-1254`.
- [ ] Reconcile verified checkboxes in PR #1255 and publish the deliberate-break
  evidence above in its body or conversation.

The GitHub connector rejected the PR-body update, evidence comment, and
`needs-human` label with `MCP tool call requires approval, but approval policy
is never`. The PR was verified **open**, with **isDraft=false**. Remote
reconciliation remains blocked by the unavailable GitHub write capability.

After all checks passed, the scoped commit attempt stopped at `git add`
(exit 128): `fatal: Unable to create
'/home/runner/work/Counter_Risk/Counter_Risk/.git/index.lock': Read-only file system`.
The new Python test changes and this evidence remain uncommitted; no branch or
pull request was created.
