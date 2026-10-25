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
