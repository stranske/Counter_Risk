# Issue 1140: saved fleet-artifact fallback regressions

This is one low-risk, test-only chunk of the continuing coverage initiative. The previous run-directory chunk is merged and independently dispositioned. Production source is unchanged; the broader issue stays open below 90 percent.

## Selection

Baseline main: `b9757030450912fe48c48e9e0ca7d34358ccb730`. Rank the last 500 production-source commits by a disclosed repair-subject proxy (whole words fix/bug/repair/regression/correct), then churn, then measured uncovered statements. This is a history proxy, not a verified escaped-incident count.

| Source | Repair-history proxy | Churn | Uncovered statements |
|---|---:|---:|---:|
| `src/counter_risk/pipeline/run.py` | 19 | 111 | 322 |
| `src/counter_risk/writers/historical_update.py` | 8 | 39 | 36 |
| `src/counter_risk/build/release.py` | 6 | 23 | 17 |
| `src/counter_risk/compute/futures_delta.py` | 6 | 19 | 9 |
| `src/counter_risk/compute/rollups.py` | 5 | 15 | 16 |

`pipeline/run.py` ranks first. Its fleet telemetry helpers missed lines 751, 754, 755, 808 and 809. The tests exercise actual persisted NDJSON rather than only helper return values: malformed and blank latency values fall through to another key, negative values fall through to a positive value, zero keeps its higher-priority position, wholly unusable metadata stays unknown, whitespace-only trace errors fall through to trimmed pipeline errors, and external report paths stay excluded while valid relative artifacts survive. No real defect was found requiring a production edit.

The negative-latency case deliberately expects the secondary value 7. Expecting 0 would be vacuous because downstream normalization clamps a wrong negative value to 0. Its actual mutation proves the fallback decision survives the artifact boundary.

## Actual mutation and restoration proof

Each named node ran once with its corresponding production behavior deliberately broken, then again after exact source-byte restoration. Every RED exited 1 with that node in pytest's failure summary; every restored GREEN exited 0 with one passing test. The runner restores source in `finally`. Complete outputs are in [the transcript](issue-1140-fleet-artifact-fallbacks-transcript.txt); per-node receipts and all per-file coverage summaries/missing-line arrays are in [the JSON](issue-1140-fleet-artifact-fallbacks.json).

| Named node | Broken behavior | Observed RED | Restored GREEN |
|---|---|---|---|
| `test_fleet_artifact_uses_first_valid_nonnegative_latency[invalid-primary]` | invalid-primary | 1 failed / exit 1 | 1 passed / exit 0 |
| `test_fleet_artifact_uses_first_valid_nonnegative_latency[blank-to-tertiary]` | blank-to-tertiary | 1 failed / exit 1 | 1 passed / exit 0 |
| `test_fleet_artifact_uses_first_valid_nonnegative_latency[negative-to-positive]` | negative-to-positive | 1 failed / exit 1 | 1 passed / exit 0 |
| `test_fleet_artifact_uses_first_valid_nonnegative_latency[zero-preferred]` | zero-preferred | 1 failed / exit 1 | 1 passed / exit 0 |
| `test_fleet_artifact_uses_first_valid_nonnegative_latency[all-invalid]` | all-invalid | 1 failed / exit 1 | 1 passed / exit 0 |
| `test_fleet_artifact_uses_pipeline_error_after_blank_trace_category` | error-category | 1 failed / exit 1 | 1 passed / exit 0 |
| `test_fleet_artifact_omits_external_report_paths` | external-reports | 1 failed / exit 1 | 1 passed / exit 0 |

Restored `src/counter_risk/pipeline/run.py` SHA256: `10038a2a20f1a6167d0e6992bc212e89546169d0a7e524350a4b2574b983723b`. Source is identical to the baseline and the prior merged safety proof.

## Validation and exact coverage

Both full local runs used Python 3.12.2 on macOS, four workers, identical source/line coverage settings and marker selection:

```sh
python3.12 -m pytest -q -n 4 -m 'not release and not slow' --cov=counter_risk --cov-report=json:<coverage-output.json>
```

| Measurement | Baseline | Candidate |
|---|---:|---:|
| Passed | 2210 | 2217 |
| Covered production statements | 10821 | 10826 |
| Total production statements | 12038 | 12038 |
| Exact percent | 89.890347234 | 89.931882372 |

Identical 106-file coverage scope; 48 release/slow deselections in both selections. The new tests add 5 covered statements; newly covered target lines: `[751, 754, 755, 808, 809]`. Focused/adjacent saved-artifact, data-quality and observability selection: 37 PASS. Black, Ruff and diff whitespace checks pass. Seven controls plus their seven restorations execute for real. No floor, exclusion, workflow or production behavior changed.

This is local line coverage. It does not establish release/slow packaging, Office/native execution, hosted delivery, live LangSmith service acceptance, branch coverage, or current-head GitHub gates. Matching keepalive owns CI/review after push. Reviewed Repo Merge Verify Closer owns expected-check topology, unchanged-head validation, zero active review threads, seven-minute review floor, guarded merge and verifier disposition.

## Acceptance follow-up

The existing seven pytest nodes now also check that a blank trace error category
with a blank or absent pipeline category persists `none` at both the top level
and in shared metadata. The external-report test checks the saved artifact count
alongside the filtered references, including an external-only input that must
persist an empty list and a count of zero. Production behavior is unchanged.

Both added behaviors have matching mutation checks: changing the error resolver's
default to `unknown-category`, or making an empty report list count as one, fails
the corresponding node. Each passes after exact source-byte restoration. Complete
RED/restored GREEN outputs and the targeted coverage output are recorded in the
[follow-up transcript](issue-1140-fleet-artifact-followup-transcript.txt).

The focused and adjacent selection passed all 37 tests on Linux with Python
3.14.7 using `-m 'not slow'` and `--cov=counter_risk.pipeline.run`. The specific
module's coverage table reports 2,511 statements, 2,197 missed, and 13 percent
(rounded). This narrowly selected run is not comparable to the full-suite
measurements above, does not replace them, and does not establish a 90 percent
repository coverage result. No new pytest nodes were added; the seven original
mutation receipts and the earlier 2,217-test measurement remain historical
evidence for the original candidate.

The repository-wide Black 26.5.1 check passed for all 369 Python files with line
length 100 and the required exclusion expression. Sandbox restrictions prevented
the default Python 3.14 worker startup; worker retries stalled. A temporary Python
3.12 launcher called Black's own `reformat_one` sequentially for every file found
by its unchanged CLI discovery. The launcher and successful gate output are in
the follow-up transcript. Focused Ruff and diff whitespace checks also passed.

Verified acceptance checklist:

- [x] Tests: saved fleet-artifact metadata fallbacks cover latency selection and blank error categories.
- [x] Tests: saved artifact references and counts exclude reports outside the run directory.
- [x] Documentation: fallback coverage, validation results, and measurement limits are recorded.

GitHub API access was unavailable during this follow-up, so the PR-body checklist
and its open/ready-for-review state could not be verified or updated remotely.
The workspace's `.git` directory is read-only, preventing a commit on this
checkout. The follow-up commit was prepared in a temporary checkout with a Git
bundle for import; this workspace's branch remains unchanged.


## Latency boundary follow-up (2026-10-06)

Reviewed commits `7ca458c` and `fd507be` before editing. Their committed evidence
already verifies the three generic measurement/regression/mutation tasks and the
historical full-scope and directory-safety criteria. The PR's automated unchecked
copies were stale. GitHub rejected the PR-body update, blocker-comment and
`needs-human` attempts with `MCP tool call requires approval, but approval policy
is never`; no remote checkbox or label was changed. The PR was observed open and
ready (`draft=false`). Its preamble still says `Closes #1140`; that should become
`Refs #1140` because the broader initiative must remain open below 90 percent.

Three new saved-artifact parameter cases protect a nonzero primary latency,
fractional input falling through to an integer secondary value, and absent
higher-priority keys falling through to the tertiary value. They assert both
top-level and shared metadata across all five persisted NDJSON records. No
production defect was reproduced; no production repair or refactor was needed.

The fresh baseline selected 2,217 items before the test edits (workers had already
collected them); the candidate selected 2,220. Both runs used Python 3.14.7 on Linux,
four workers, `--cov=counter_risk`, and `-m 'not release and not slow'`, with 48
deselections each. Candidate coverage used a separate `COVERAGE_FILE` to keep the
data independent. Full outputs and collection are appended to the companion
transcript (only trailing whitespace is normalized); all 106 per-file summaries and missing-line arrays,
the refreshed ranking, and per-node receipts are in the JSON follow-up object.

| Measurement | Baseline | Candidate |
|---|---:|---:|
| Test outcome | 2216 passed, 1 skipped in 989.51s (0:16:29) | 2219 passed, 1 skipped in 700.37s (0:11:40) |
| Covered statements | 10825 | 10825 |
| Total statements | 12038 | 12038 |
| Missing statements | 1213 | 1213 |
| Exact coverage percent | 89.923575344742 | 89.923575344742 |

Actual change: **+0 covered statements** and
**+0.000000000000 percentage points**. These tests
strengthen behavioral boundaries rather than claim a line-coverage gain. The
starting exact percentage is below 90; the broader initiative remains open.

Ranking uses the last 500 production-source commits at starting HEAD `fd507be`,
whole-word repair subjects (`fix|bug|repair|regression|correct`), then churn, then
measured missing statements. The history proxy is not a verified incident count.

| Source | Repair-history proxy | Churn | Missing statements |
|---|---:|---:|---:|
| `src/counter_risk/pipeline/run.py` | 19 | 111 | 317 |
| `src/counter_risk/writers/historical_update.py` | 8 | 39 | 36 |
| `src/counter_risk/build/release.py` | 6 | 23 | 17 |
| `src/counter_risk/compute/futures_delta.py` | 6 | 19 | 9 |
| `src/counter_risk/compute/rollups.py` | 5 | 15 | 16 |

Mutations ran in an isolated checkout of the same starting HEAD with the new test
file copied in, so neither full coverage run could observe mutated source. Each
control failed its named assertion and passed after exact byte restoration in
`finally`. The last two controls repeat the prior follow-up assertions so their
machine-readable receipts also accompany the main evidence.

| Exact node | Actual source mutation | RED | Restored GREEN |
|---|---|---|---|
| `tests/pipeline/test_fleet_artifact_fallbacks.py::test_fleet_artifact_uses_first_valid_nonnegative_latency[primary-preferred]` | `if parsed >= 0 and (key != "LANGSMITH_TRACE_LATENCY_MS" or parsed == 0):` | 1 failed / exit 1 | 1 passed / exit 0 |
| `tests/pipeline/test_fleet_artifact_fallbacks.py::test_fleet_artifact_uses_first_valid_nonnegative_latency[fractional-to-secondary]` | `parsed = int(float(value))` | 1 failed / exit 1 | 1 passed / exit 0 |
| `tests/pipeline/test_fleet_artifact_fallbacks.py::test_fleet_artifact_uses_first_valid_nonnegative_latency[absent-to-tertiary]` | `if raw is None: return None` | 1 failed / exit 1 | 1 passed / exit 0 |
| `tests/pipeline/test_fleet_artifact_fallbacks.py::test_fleet_artifact_uses_pipeline_error_after_blank_trace_category` | `return "unknown-category"` | 1 failed / exit 1 | 1 passed / exit 0 |
| `tests/pipeline/test_fleet_artifact_fallbacks.py::test_fleet_artifact_omits_external_report_paths` | `"report_artifact_count": len(report_refs) or 1,` | 1 failed / exit 1 | 1 passed / exit 0 |

Restored pipeline SHA256: `10038a2a20f1a6167d0e6992bc212e89546169d0a7e524350a4b2574b983723b`.
Restored observability SHA256:
`461c3ff1af573bb92a043b5a03018edbb60975051470aad5c5873f62a0d7283c`.

Focused artifact/data-quality/observability tests: **40 passed**; directory-safety
tests: **20 passed**. Targeted `--cov=counter_risk.pipeline.run -m 'not slow'`
reports **314 / 2,511 statements (13% rounded)**; it is not a package measurement.
Black formatted the changed Python file, Ruff passed, and the exact whole-repo
Black CLI check passed for **369 files** with the required line length/exclusions.
Sandbox worker execution stalled; a temporary Python 3.12 serial launcher used
Black 26.5.1's unchanged CLI discovery and `reformat_one`, populated a writable
cache, and then the standard Black command passed. The launcher/output are in
the transcript. No formatting, marker, coverage or workflow configuration changed.

The exact `python3.12 -m pytest` acceptance command could not run because that
interpreter has no pytest installed. Python 3.14 validation is explicitly recorded
as such; the Python 3.12 acceptance checkbox remains unchecked. Release/slow,
Office/native, hosted/live LangSmith, branch coverage and current-head GitHub
checks remain outside these local measurements.

Locally verified task reconciliation:

- [x] Package measurement and ranked target selection.
- [x] Focused regressions with no reproduced production defect to repair.
- [x] Every new parameter node failed an actual source mutation and passed after exact restoration.
- [x] Directory-safety suite and identical-scope baseline/candidate evidence.
- [ ] Python 3.12 saved-artifact acceptance command (pytest unavailable).
- [ ] Live PR checklist, closing-reference correction and needs-human/comment updates (GitHub writes rejected).
