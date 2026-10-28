Fresh local verification of the provenance fixture change on Python 3.14.8.
The branch already reused `_write_scope_workflow_config`; this follow-up checks
the complete manifest hash mapping in every optional-input scenario, including
all seven required source hashes. Original mutation, activation, collision and
generated-image assertions remain in place. Production files are unchanged.

These measurements use the runner interpreter at
`/opt/hostedtoolcache/Python/3.14.8/x64/bin/python`; this checkout has no virtualenv.
They independently verify the behavior described by the task, rather than
authenticate its historical timings of 186.41s/0.60s, 2.83s, or 219.55s/225.94s.
They make no claim about hosted whole-Gate duration or the seven daily Gate
measurements required for source closure.

- [x] Same-host named test comparison: the parent test at `6112213` passed in
  211.24s call / 212.14s total ([baseline.log](baseline.log)). With the small real
  inputs and the additional assertions, the restored test passed in 0.39s call /
  0.74s total ([restored-green.log](restored-green.log)). Both ran with
  `python -m pytest tests/pipeline/test_run_pipeline.py::test_optional_input_provenance_hashes -m "not slow" --durations=1`.
- [ ] All 11 focused provenance, limit-scope and header-reader cases pass in
  1.54s ([focused.log](focused.log)). Black 26.10.1 passes for the changed file
  ([black-changed.log](black-changed.log)); Ruff and `git diff --check` pass.
  The required repository-wide Black check is blocked by the sandbox's
  forkserver socket restriction and stalling alternative worker configurations.
  This combined task remains unchecked. Commands are below.
- [x] Disconnecting external screenshot hashing at the real pipeline call site
  caused the same named test to fail on the missing `screenshot_inputs.slide1`
  hash ([mutation-red.log](mutation-red.log)). Exact-byte production restoration
  passed ([restored-green.log](restored-green.log)). [mutation.json](mutation.json)
  records the replacement, command, exit codes and matching original/restored
  SHA-256 values. No production mutation remains.
- [x] A bounded partial cProfile run of the parent test was interrupted after
  diagnosis, with no test verdict ([profile-interrupted.log](profile-interrupted.log)).
  `apply_stylesheet` accumulated 41.55s in a 55.27s profile
  ([profile-stylesheet.log](profile-stylesheet.log)). The interrupt was requested
  at 45s; profiling and interrupt cleanup contributed to elapsed time. The
  profile wrapper returned zero because it did not propagate pytest's interrupt
  status; that process status is not evidence of a test pass.

Validation commands, using the same runner interpreter and installed tools:

```sh
python -m pytest \
  tests/pipeline/test_run_pipeline.py::test_optional_input_provenance_hashes \
  tests/pipeline/test_run_pipeline.py::test_all_programs_limit_scope_propagates_to_pipeline_and_exit \
  tests/pipeline/test_header_extraction_boundaries.py \
  -m "not slow" --durations=11
python -m black --line-length 100 tests/pipeline/test_run_pipeline.py
BLACK_NUM_WORKERS=1 black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
python -m ruff check tests/pipeline/test_run_pipeline.py
git diff --check
```

Black's default process pool could not bind its forkserver socket in the sandbox.
The one-worker attempt stalled and was interrupted; explicit fork also stalled.
A final explicit-spawn attempt was bounded to 45s. These incomplete attempts
are not formatting passes. Published log trailing whitespace is normalized;
production restoration hashes cover exact file bytes.

Committing is also blocked: `.git` is mounted read-only, and `git add` failed
with `Unable to create .../.git/index.lock: Read-only file system`. No commit
was created and no push was attempted.

## 2026-10-25 follow-up

The named test now changes workbook bytes before changing screenshot bytes,
checking that each mutation leaves the other source's hash unchanged. All
original source activation, mutation, generated-image exclusion, collision and
manifest assertions remain, as do production pipeline calls.

- The 11 focused tests pass in 1.81s, including the named test at 0.38s call.
- Disconnecting external screenshot hashing again fails the named test
  ([independent-mutation-red.log](independent-mutation-red.log)); exact-byte
  production restoration passes at 0.38s call / 0.70s total
  ([independent-restored-green.log](independent-restored-green.log)). The restored
  production SHA-256 is
  `6932dff548065ef429e7d99f645900884c4aa0d80d2fc4d6f13d1febeed745b4`.
- Changed-file Black, Ruff and `git diff --check` pass. Repository-wide Black
  with one worker still times out; its diagnostic stack waits in the event
  loop. An interrupted diagnostic printed 374 unchanged files, but exited 124;
  this is not a successful formatting gate.
- `git add tests/pipeline/test_run_pipeline.py` fails because `.git` is
  read-only. No commit or push was made.

Hosted comparison, collected through read-only GitHub API calls:

| Measurement | [Before](https://github.com/stranske/Counter_Risk/actions/runs/40160750372) | [After](https://github.com/stranske/Counter_Risk/actions/runs/40210271632) |
| --- | ---: | ---: |
| Gate, run start through final job completion | 25m22s | 18m25s |
| Python 3.14 job | 24m38s | 16m17s |
| Python 3.14 pytest step | 19m40s | 12m18s |
| Python 3.14 dependency installation | 4m12s | 3m04s |
| Python 3.13 job | 11m24s | 17m37s |

Gate elapsed decreases 417s (27.4%), and the Python 3.14 job decreases 501s
(33.9%). [hosted-comparison.json](hosted-comparison.json) records source SHAs,
timestamps, job conclusions and called-workflow revisions. Elapsed excludes
metadata updates after the last job finishes. The baseline bottleneck is pytest
(1180 of 1478 Python 3.14 job seconds), followed by dependency installation
(252s). Local profiling above identifies repeated openpyxl stylesheet reads in
the provenance test. The called workflow runs the existing test selection with
coverage disabled; lint, mypy and both Python versions remain required.

Both hosted runs passed. At remote head `fb3122f`, both Python jobs, lint,
mypy, gate-summary and `Gate / gate` passed. Python 3.13 becomes the longest
job after the change. These measurements are observational: upstream reusable
workflow revisions and dependency/cache timings differ, so the entire Gate
reduction cannot be attributed to the provenance test. This follow-up test edit
has not run on hosted Gate. Gate remains above ten minutes, and the seven daily
Health 85 p50 measurements remain pending; issue #1189 remains open.

Automatic approval review rejected updating PR #1191's body because approval
policy is `never`. The live checklist could not be reconciled. The concrete
replacement [pr-body.md](pr-body.md) checks off the five criteria supported by
the existing remote head and leaves the seven-day Health 85 criterion open.
Publishing that body would attach the hosted measurements; it does not claim
the uncommitted follow-up already passed hosted Gate. No protected files were
changed.

## 2026-10-28 cursor opener

Hosted Codex keepalive on PR #1207 failed twice with `No output captured` on
head `5edf461` (terminal runner errors, zero task progress). Cursor opener
re-ran the named acceptance command locally: **3.09s call**, 1 passed. Updated
PR checklist and applied `agent:retry`. Gate Followups requires a separate
manual `agents-81-gate-followups.yml` dispatch with `pr_number=1207` and
`force_retry=true`; full Python 3.14 Gate re-run requested via branch sync.

After merge to `main` at head `5aa464b`, Gate run
[40733914407](https://github.com/stranske/Counter_Risk/actions/runs/40733914407)
passed with **Python CI skipped** (merge commit touched docs only). PR #1207
carries `verify:full`; a follow-up commit touching the provenance test path
re-triggers full Python 3.14. Hosted Codex on `5aa464b` failed three times
with `No output captured` (reservations through 2026-10-28T17:31Z); cursor
opener owns bounded recovery without overlapping writers.

## 2026-10-28T19:15Z cursor opener — `verify:full` removed

Gate run [40743163671](https://github.com/stranske/Counter_Risk/actions/runs/40743163671)
on head `9ede890` reported `force-full` classification: every category including
`is-docs-only` was true, so **Python CI / python 3.14** was skipped despite the
`verify:full` label. Counter_Risk `path-classifier` treats `force-full` as
all categories enabled; `pr-00-gate.yml` still requires `is_docs_only != true`
for Python CI. Remove `verify:full` from PR #1207, then push a substantive
follow-up commit to the same PR branch to trigger a fresh `pull_request`
`synchronize` event. That event classifies the complete PR diff
(`tests/pipeline/test_run_pipeline.py` + evidence docs) normally and runs hosted
Python 3.14. Do not use a manual Gate dispatch for this validation:
`pr-00-gate.yml` also enables `force-full` for every `workflow_dispatch` event,
even without the label, so that path still skips Python CI. Local named test: **8.49s call**, 1 passed
(cursor opener, 2026-10-28). Keepalive Codex on `365cb6ce` failed at **Setup
Codex auth** (fleet `CODEX_AUTH_JSON` refresh — Workflows #4281); no overlapping
writer; cursor recovery only.


## 2026-10-28 Codex opener — hosted validation receipt

The ordinary PR event at head `d36ae9a49e9041eed8a007012123d4f890f5971b`
produced [Gate 40752236077](https://github.com/stranske/Counter_Risk/actions/runs/40752236077).
Both `Python CI / python 3.13` and `Python CI / python 3.14`, Ruff, mypy,
`gate-summary`, and `Gate / gate` completed successfully. This is executed
Python CI evidence, rather than a skipped-job or manual-dispatch receipt.
The recovery instructions above now distinguish the PR synchronization event
from the manual Gate path. The seven daily Health 85 p50 measurements remain
pending on source issue #1189.
