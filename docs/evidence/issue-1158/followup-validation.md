# Registry limit alias follow-up

The production fix and Configuration sentence already exist in base commit
`247bb666d3e5777c8df7438d81813824cc49195c`. This follow-up expands the regressions
and verifies the remaining checklist against that implementation.

- [x] `_canonical_entity_key` uses `resolve_clearing_house` for clearing houses
  and `resolve_counterparty` for FCMs.
- [x] Both `check_limits` and `find_missing_limit_entities` call that helper.
- [x] Parameterized CME, ICE, and FCM tests compare complete breach records,
  actual values, and missing results for display names and aliases under both
  absolute and percentage limits. Split CME aliases aggregate to 60%.
- [x] Unknown clearing houses preserve missing findings; disabled limits are
  ignored with their registered alias present and with the entity absent.
- [x] Pipeline tests verify identical CSV bytes and manifest breach summaries
  under strict missing policy for canonical, alias-only, and split-alias rows.
- [x] Configuration documents registry resolution before comparison.

The pipeline regression starts from fixed parsed rows, stubbing date-header
discovery and unrelated historical reconciliation. Limit exposure construction,
missing checks, breach computation, CSV writing, and manifest generation remain
real. Its missing-warning assertion now matches the actual warning wording.

Acceptance verification:

- [x] `pytest tests/compute/test_limits.py -k alias -m "not slow"`: 36 passed.
- [x] `pytest tests/pipeline/test_run_pipeline.py -k limit -m "not slow"`:
  7 passed, including canonical/alias CSV and manifest equality.
- [x] Named compute and pipeline cases verify unknown clearing houses warn or
  raise according to strict mode, and disabled limits stay ignored.
- [x] `rg -n "resolve_clearing_house" src/counter_risk/compute/limits.py`
  matches the import and resolver selection.
- [x] Compute, limits configuration, name registry, and limit documentation
  tests: 113 passed with `-m "not slow"`.
- [x] Disconnecting FCM/clearing-house resolution in the actual scope helper
  causes 7 regression failures. Restoring the exact original bytes yields
  7 passes. See `followup-mutation.json` and the red/green logs.

The appendix's parser anchor is stale: `parsers/cprs_fcm.py` has no corresponding
change to disconnect. The deliberate break uses `compute/limits.py`, as specified
by the corrected Additional PR task, and verifies the described suppressed breach.

Black's repository-wide check passes for all 377 files; Ruff and `git diff
--check` also pass. The Black CLI used one worker plus a temporary event-loop
polling shim because the sandbox blocks executor socket wakeups. The shim lives
outside the repository and does not change formatting behavior.

The `followup-*.txt` files capture test and formatting output. The accompanying
manifest binds these results to the current source and tests. No hosted CI or
review result is implied by these local checks.

Final acceptance follow-up:

- [x] `rg -n "resolve_clearing_house" src/counter_risk/compute/limits.py`
  returns matches at lines 14 and 96, satisfying the remaining acceptance item.
- Expanded the registered futures alias regression to include all supported
  clearing-house columns (`clearing_house`, `clearinghouse`, `ch`) and FCM columns
  (`fcm`, `fcm_name`) for absolute and percentage limits.
- Disconnecting registry resolution in `compute/limits.py` yields 16 failures;
  restoring the exact original source yields 16 passes.
- Verification: 51 alias tests, 127 compute/configuration/registry tests, and
  8 pipeline limit tests pass with `-m "not slow"`. Ruff and `git diff --check`
  pass. Black's repository-wide check passes for all 377 files using a serial
  formatting dispatcher to avoid the sandbox's executor restrictions.
