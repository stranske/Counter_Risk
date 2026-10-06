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
