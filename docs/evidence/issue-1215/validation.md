# Verification and publication status

This records the earlier iteration. See [root-discovery-validation.md](root-discovery-validation.md) for the follow-up on `c80d63c`, including two additional test cases and current publication blockers.

Environment: Python 3.14.9, pytest 9.2.0, Black 26.10.1, Ruff 0.17.3.

- Reviewed `ba3969a` and `4af5ae2`: eight unique test files, no production changes.
- Base snapshot `/tmp/1216-before` from `faad152`: `pytest tests/ -n 2 -m "not slow"` with targeted coverage for the eight issue modules: **2478 passed, 1 skipped**.
- Candidate snapshot `/tmp/1216-candidate` from `4af5ae2` plus the four new manifest tests: same command and module coverage flags: **2622 passed, 1 skipped**.
- Final restored workspace, eight affected test modules: **189 passed** with `-m "not slow"`.
- Focused manifest suite: **151 passed**, 99% line-plus-branch coverage, versus 147 passed and 95% before the four tests.
- Focused schema suite: **70 passed**, 100% line-plus-branch coverage.
- Every added parametrized case (144 total) failed under at least one real source mutation and passed after restoration. JUnit collection/fixture errors were rejected as witnesses. Exact mutations and red/green results are in the neighboring evidence files.
- `black --line-length 100 tests/pipeline/test_manifest.py`: passed, unchanged.
- `black --check --line-length 100 tests/pipeline/test_manifest.py`: passed.
- `ruff check --output-format github --extend-exclude .workflows-lib .`: passed repository-wide, using the reusable CI job's configured flags.
- `git diff --check`: passed.
- `git diff --exit-code -- src`: passed; all deliberate source changes were reverted.
- The candidate snapshot's manifest source and test bytes match the delivered workspace; all other production source files are unchanged from HEAD.

## Repository-wide Black gate passed

Both the required command and the reusable CI job's exclude pattern completed with exit 0, reporting **401 files would be left unchanged**:

```sh
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/1216-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/1216-black-cache black --check --line-length 100 --exclude '(\.venv|\.workflows-lib|node_modules)' .
```

The first default-worker attempt failed because Python 3.14's multiprocessing forkserver could not bind its local worker socket in this sandbox (`PermissionError: [Errno 1] Operation not permitted`). A single-worker attempt stalled and was interrupted (exit 130); bounded diagnostic runs also timed out. A diagnostic using a writable cache reported every file unchanged and populated Black's normal cache. Both subsequent direct commands above then exited successfully. Timed-out diagnostics were not counted as successful gate runs.

No formatter configuration or security restrictions were changed. Black's normal cache was not edited manually. The changed Python file also passes Black independently.

## Publication blockers

- `git add tests/pipeline/test_manifest.py` failed: `fatal: Unable to create '/home/runner/work/Counter_Risk/Counter_Risk/.git/index.lock': Read-only file system`. Therefore this run could not commit or push the verified changes.
- The authorized PR-body reconciliation call was rejected: `MCP tool call requires approval, but approval policy is never`. No alternate API path was used to bypass that rejection.
- [pr-body.md](pr-body.md) contains the concrete replacement PR description, coverage shortfall, remaining paths, and verified contract checkboxes. It has not been applied remotely.
- PR #1216 was rechecked and remains open, ready for review (`isDraft=false`), on the pre-existing head `4af5ae2`. That head's Gate run 40830517824 succeeded; CI has not run the four additional tests from this workspace.

This is a verified local partial delivery: 176 additional covered lines across the targets, four short of the 180-unit aim. The issue's CI baseline remains authoritative. No repository-wide 90% claim is made.
