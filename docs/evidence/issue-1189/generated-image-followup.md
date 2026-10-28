## 2026-10-28 generated-image provenance follow-up

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

Publishing the reconciled PR body and adding `needs-human` were both rejected:
`MCP tool call requires approval, but approval policy is never`.
The proposed body is saved in [pr-1207-body.md](pr-1207-body.md); the live
checklist was not changed. PR #1207 was verified open with `draft=false`.
