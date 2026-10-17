# Keepalive verification — 2026-10-17

Base: `832b093` on Linux with Python 3.14.8. The first unchecked implementation
tasks in the supplied checklist already exist in this base; this round extends
their tests rather than duplicating the helper or changing screenshot precedence.

The exporter-bound regression now checks the authoritative source and positive,
zero, and negative overrides in both CH and FCM copies. It also verifies that
unadjusted variants remain byte-identical and all original inputs retain their
SHA-256 hashes. The native Office test now compares decoded pixels, avoiding a
false pass caused only by PNG metadata or compression changes.

Verified task state (duplicate checklist entries consolidated):

- [x] Run-local adjusted reporting workbook helper: all five adjusted tests pass.
- [x] Exporter takes the run-local workbook paths: all four exporter cases fail
  when the original configured-workbook route is temporarily restored.
- [x] Exporter regression checks adjusted CIBC cash in both CH and FCM.
- [x] Real pipeline agreement and explicit screenshot precedence:
  `pytest tests/pipeline/test_run_pipeline.py -k screenshot -m "not slow"`
  reports 2 passed (`pipeline-screenshot.log`). Exporter input, historical Cash,
  and totals agree; both generated-image and explicit-image selection pass.
- [x] No-adjustment copies and existing screenshot replacement tests pass:
  `pytest tests/pipeline/test_cprs_screenshot_generation.py tests/test_pipeline_screenshot_replacement.py -m "not slow"`
  reports 25 passed and 1 Office skip (`focused.log`).
- [x] Deliberate-break gate: 5 passed before, 4 failed / 1 passed on the original
  route, and 5 passed after byte-identical source restoration. See the three
  gate logs and `break-proof.json` for source/test hashes and the exact command.
- [x] Windows platform-handoff brief updated in `../OFFICE_HANDOFF.md`, including
  the command, expected assertions, evidence to retain, and explicit skip status.
- [ ] Native Office execution: unavailable on Linux; this is not a rendering pass.

Black's repository-wide check passed for 379 files (`black.log`). Default worker
creation was denied by the sandbox; the single-worker event loop also stalled.
The successful check used one worker and a temporary runtime event-loop timer to
keep it progressing. No formatting rules, source files, or exclusions were
changed by that runtime workaround. Ruff and `git diff --check` also pass.

Staging failed because the workspace's `.git` is read-only:
`fatal: Unable to create '.git/index.lock': Read-only file system`.
The test changes and evidence remain available for a writable checkout to commit.
A temporary local clone at `/tmp/counter-risk-1159-commit` preserves a commit of
these changes; its exported patch is `/tmp/counter-risk-1159-keepalive.patch`.
The original workspace branch remains unchanged.
