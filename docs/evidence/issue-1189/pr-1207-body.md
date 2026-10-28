Refs #1189

Reuse minimal real XLSX/PPTX helpers in `test_optional_input_provenance_hashes` so Gate no longer loads style-heavy archived workbooks during provenance checks. Preserves active-source, byte-mutation, generated-image exclusion, and manifest assertions; production pipeline calls unchanged.

**Measurements:** named test **~3.1s call** locally (cursor opener, 2026-10-28) vs **211s+** baseline in `docs/evidence/issue-1189/baseline.log`. Prior hosted full Gate on head `fb3122f` documented in `docs/evidence/issue-1189/hosted-comparison.json`. Initial Gate on PR open skipped Python CI. After removing `verify:full`, the ordinary PR event on `d36ae9a` ran Python 3.13/3.14 successfully (Gate 40752236077). Manual Gate dispatch enables `force-full` and skips Python CI; a PR synchronize event is required. Documentation correction pushed at `e66cf4a`; new-head checks remain pending.

**Hosted keepalive:** Codex runner failed twice with `No output captured` on head `5edf461` (reservations `a6641d10`, `28c94f01`); opener recovery updates checklist and retriggers CI without overlapping writers.

## Test plan
- [x] `PYTHONPATH=src python -m pytest tests/pipeline/test_run_pipeline.py::test_optional_input_provenance_hashes -q -o addopts= --durations=3`
- [x] Hosted Gate Python 3.13/3.14 executed and passed on `d36ae9a` (40752236077); new documentation head awaits its own checks
- [ ] Health 85 seven-day p50 series remains future acceptance on source issue

<!-- pr-preamble:start -->
<!-- meta:issue:1189 -->
> **Source:** Issue #1189

Refs #1189

<!-- pr-preamble:end -->

<!-- auto-status-summary:start -->
## Automated Status Summary
#### Scope
The trailing-seven-day Gate p50 is 19.97 min against a
10 min target. Longest observed job: [Python CI / python 3.14](https://github.com/stranske/Counter_Risk/actions/runs/40160750372/job/121071665022)
(24.63 min), in `.github/workflows/pr-00-gate.yml`.
Current share: 39.63%; distance: 0.997;
drainable_in: 7 days.

#### Tasks
- [x] Inspect `Python CI / python 3.14` in `.github/workflows/pr-00-gate.yml` and its called workflow using the linked run; identify the duration bottleneck.
- [x] In `tests/pipeline/test_run_pipeline.py::test_optional_input_provenance_hashes`, replace unrelated large archive workbook inputs with the existing real minimal XLSX/PPTX helper while preserving every active-source, byte-mutation, generated-image-exclusion and manifest assertion; retain production pipeline calls.
- [x] Compare Gate durations before/after and attach run URLs and measurements.

#### Acceptance criteria
- [x] `PYTHONPATH=src python -m pytest tests/pipeline/test_run_pipeline.py::test_optional_input_provenance_hashes -q -o addopts= --durations=3` collects one passing test, records a measured before/after duration reduction in the PR, and still fails when external screenshot hashing is temporarily disconnected; restore and pass again.
- [ ] `.github/workflows/pr-00-gate.yml` passes with required checks preserved after the change.
- [ ] Health 85 reports trailing-seven-day Gate p50 at or below 10 min for seven consecutive daily measurements, then closes this issue with the dated p50 series.

<!-- auto-status-summary:end -->


### Verified follow-up (2026-10-28)

The first unchecked task was reverified against the linked Python 3.14 job
[121071665022](https://github.com/stranske/Counter_Risk/actions/runs/40160750372/job/121071665022).
Its pytest step took **1180s of 1478s (79.8%)**; dependency installation took
252s. The Gate caller uses `reusable-10-ci-python.yml@main`, with Python
3.13/3.14, `coverage: false` and the existing test marker selection. The called
workflow at `58ff03379b271c51f941d6c6fe42636f2947c4a8` constructs the pytest
command and uses xdist when available. Existing local profiling identifies
repeated openpyxl stylesheet reads in the provenance test.

- [x] Inspect the linked job and its called workflow; identify the bottleneck.
- [x] Compare hosted durations and record run URLs and measurements below.
- [x] Verify the named test passes, detects disconnected screenshot hashing,
  and passes again after exact-byte production restoration.
- [ ] Run hosted Gate on this follow-up test change.
- [ ] Complete the required repository-wide Black gate and commit the source change.
- [ ] Observe seven consecutive daily Health 85 trailing-seven-day p50 values
  at or below ten minutes before source issue #1189 closes.

The test now regenerates an intermediate screenshot with different real PNG
bytes and verifies that the complete manifest hash mapping remains identical.
It also verifies that the explicit external screenshot still wins the path
collision. All prior active-source, workbook/screenshot byte mutation,
generated-image exclusion and manifest assertions remain. Production pipeline
calls and workflow files are unchanged.

Validation on Python 3.14.9:

- Before this follow-up, the named minimal-fixture test passed at 0.44s call /
  1.61s total. The existing archive-input baseline is 211.24s call /
  212.14s total in [baseline.log](baseline.log), recorded on Python 3.14.8;
  this is not a fresh same-host comparison.
- All 11 focused provenance, limit-scope and header-boundary cases pass in
  2.23s; the strengthened provenance test takes 0.48s call.
- Temporarily disconnecting external screenshot hashing produces the expected
  missing `screenshot_inputs.slide1` failure, exit 1
  ([red log](generated-image-mutation-red.log)).
  Exact-byte restoration passes at 0.49s call / 0.86s total
  ([green log](generated-image-restored-green.log)).
  [Mutation metadata](generated-image-mutation.json) records the command,
  exit codes and matching production SHA-256 values.
- Changed-file Black 26.10.1 and Ruff pass.
- Required repository-wide Black fails with `PermissionError: [Errno 1]
  Operation not permitted` while binding the multiprocessing forkserver
  socket. `BLACK_NUM_WORKERS=1 timeout 60s black --check --line-length 100
  --exclude '(\.workflows-lib|node_modules)' .` exits 124; its interrupted
  output says 394 files unchanged, which is not a successful formatting gate.
- `git add tests/pipeline/test_run_pipeline.py` fails creating
  `.git/index.lock`: read-only filesystem. No commit or push was made.
  Complete Black and commit in a writable checkout, then validate with an
  ordinary PR synchronize event. No workflow edit is required.

| Measurement | [Before: 40160750372](https://github.com/stranske/Counter_Risk/actions/runs/40160750372) | [Latest executed: 40752236077](https://github.com/stranske/Counter_Risk/actions/runs/40752236077) |
| --- | ---: | ---: |
| Gate, run start through last job completion | 25m22s | 3m15s |
| Python 3.14 job | 24m38s | 1m46s |
| Python 3.14 pytest step | 19m40s | 54s |
| Python 3.14 dependency installation | 4m12s | 3s |
| Python 3.13 job | 11m24s | 2m11s |

[Latest comparison data](hosted-latest-comparison.json) records source head,
workflow revision, timestamps and job conclusions. The latest run on
`d36ae9a49e9041eed8a007012123d4f890f5971b` passed both Python versions, Ruff,
mypy, gate-summary and `Gate / gate`. It predates this local test change.
Workflow revisions, dependency/cache timings and collected test counts differ
(baseline Python 3.14: 2454 passed, 2 skipped; latest: 2434 passed, 1 skipped).
The full improvement cannot be attributed to this fixture change alone.
One hosted run below ten minutes does not satisfy the seven-day p50 criterion.
