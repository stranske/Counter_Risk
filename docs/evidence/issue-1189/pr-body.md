The provenance hashing test repeatedly loaded style-heavy archived workbooks during header/date extraction. It was the slowest test in Gate run 40160750372 (421.299s on Python 3.14), although its assertions cover optional input hashes rather than workbook formatting.

Reuse the existing helper that writes small real XLSX and PPTX files. All original active-source, source-byte mutation, generated-image exclusion, explicit screenshot collision and manifest assertions remain. Production header/date reads and pipeline/manifest calls still execute; production code and other workbook integration tests are unchanged.

Refs #1189. Health 85 retains source closure after seven daily Gate p50 measurements at or below ten minutes.

Validation with the repository-selected virtualenv:
- Same-host named test: 186.41s call / 187.27s total before; 0.60s call / 1.67s total after. This is a local test comparison, not a hosted whole-Gate duration claim.
- 11 focused provenance, limit-scope and header-reader tests pass in 2.83s. Black26.10.1, Ruff and git diff --check pass.
- Temporarily disconnect external screenshot hashing in the real pipeline: the same provenance test FAILS. Exact-byte restoration: PASS. No production change remains.
- A bounded partial cProfile run attributed 219.55 of 225.94 seconds to openpyxl stylesheet application; it was interrupted after diagnosis and is not a test verdict.

Commands:
```sh
PYTHONPATH=src python -m pytest tests/pipeline/test_run_pipeline.py::test_optional_input_provenance_hashes -q -o addopts= --durations=3
PYTHONPATH=src python -m pytest tests/pipeline/test_run_pipeline.py::test_optional_input_provenance_hashes tests/pipeline/test_run_pipeline.py::test_all_programs_limit_scope_propagates_to_pipeline_and_exit tests/pipeline/test_header_extraction_boundaries.py -q -o addopts=
```

Hosted Gate passed at `fb3122ff892cafc0b6130f49b5675d8dd631530b`; any subsequent source commit needs its own Gate result. The seven-minute review floor remains required. Intake returned FREE and UNGATED, so automerge is not enabled. The source issue's formatting pause was removed only after its repaired body passed the repository format validator; its Health85 acceptance criterion remains.


Hosted measurements collected on 2026-10-25 (UTC):

| Measurement | [Before: 40160750372](https://github.com/stranske/Counter_Risk/actions/runs/40160750372) | [After: 40210271632](https://github.com/stranske/Counter_Risk/actions/runs/40210271632) |
| --- | ---: | ---: |
| Gate elapsed, run start through final job completion | 25m22s | 18m25s |
| Python 3.14 job | 24m38s | 16m17s |
| Python 3.14 pytest step | 19m40s | 12m18s |
| Python 3.14 dependency installation | 4m12s | 3m04s |
| Python 3.13 job | 11m24s | 17m37s |

Gate elapsed fell 417s (27.4%); the Python 3.14 job fell 501s (33.9%). API timestamps and all job verdicts are in `docs/evidence/issue-1189/hosted-comparison.json`. Elapsed uses `run_started_at` through the final job's `completed_at`, excluding later metadata updates. Both runs passed. Python 3.13 is the longest after-change job. These are observed hosted measurements, not a controlled attribution of all savings to this test: reusable-workflow revisions differ, as do dependency-install timings and runner/cache conditions.

The baseline bottleneck is pytest (1180 of 1478 Python 3.14 job seconds, 79.8%), followed by dependency installation (252s). The called workflow was `stranske/Workflows/.github/workflows/reusable-10-ci-python.yml` at `58ff03379b271c51f941d6c6fe42636f2947c4a8`; the after run used `056470c8ef75118cade2f9d5fb438907d1ff2dad`. Both ran Python 3.13/3.14 with the existing test selection. Local profiling identifies repeated openpyxl stylesheet reads in this provenance test; the tiny real fixtures remove those unrelated reads while retaining production boundaries.

Follow-up validation separates workbook and screenshot byte mutations and checks unchanged-source hash stability. All 11 focused cases pass in 1.81s; disconnecting external screenshot hashing fails the named test, exact-byte restoration passes in 0.38s call / 0.70s total. Production source is restored. This follow-up is currently uncommitted because `.git` is read-only; repository-wide Black attempts timed out, so no full formatting pass is claimed. Changed-file Black, Ruff and diff checks pass.

The existing hosted head passes Python 3.13, Python 3.14, Ruff, mypy, gate-summary, and the `Gate / gate` status. Workflow files and required checks are unchanged. Gate remains above ten minutes. The seven consecutive daily Health 85 p50 measurements and source-issue closure remain pending.

<!-- pr-preamble:start -->
<!-- meta:related-issue:1189 -->
> **Source:** Issue #1189

Related to #1189

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
- [x] `.github/workflows/pr-00-gate.yml` passes with required checks preserved after the change.
- [ ] Health 85 reports trailing-seven-day Gate p50 at or below 10 min for seven consecutive daily measurements, then closes this issue with the dated p50 series.

<!-- auto-status-summary:end -->
