# Issue #1127 fork Gate deliberate-break evidence

This evidence closes the transcript gap tracked by issue #1130 for merged PR
#1128. The regression lives in `tests/test_gate_commit_status_fork_tolerance.py`,
and the fork read-only tolerance lives in `.github/workflows/pr-00-gate.yml` in the
`Report Gate commit status` catch block.

## Procedure

1. Run the focused gate fork tolerance suite on unmodified `main`.
2. Temporarily force `readOnlyForkToken` to `false` in the workflow catch block
   (equivalent to reverting the fork tolerance without touching other paths).
3. Run the identical pytest command and capture the expected fork-case failures.
4. Restore the production workflow exactly and rerun the identical command.
5. Record literal command transcripts below.

Executed from commit `ff4bc1958dd6c1ce48952e1c63fa60d16402fa2e` on branch
`codex/issue-1130-gate-fork-deliberate-break-evidence` with Python 3.12.2.

## RED — fork tolerance deliberately disabled

Temporary mutation in `.github/workflows/pr-00-gate.yml`:

```diff
-              const readOnlyForkToken =
-                error?.status === 403 && isForkPullRequest && !hitRateLimit;
+              const readOnlyForkToken = false;
```

Command:

```console
$ python3 -m pytest tests/test_gate_commit_status_fork_tolerance.py -q
collected 8 items

tests/test_gate_commit_status_fork_tolerance.py FFFF....                 [100%]

=================================== FAILURES ===================================
________________ test_fork_read_only_403_does_not_fail_the_gate ________________
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

_______________ test_fork_read_only_403_reports_the_real_verdict _______________
E       AssertionError: assert 'read-only' in ''

______________ test_fork_read_only_403_preserves_failure_verdict _______________
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

_____________ test_deleted_fork_read_only_403_reports_the_verdict ______________
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

=========================== short test summary info ============================
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_does_not_fail_the_gate
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_reports_the_real_verdict
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_preserves_failure_verdict
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_deleted_fork_read_only_403_reports_the_verdict
========================= 4 failed, 4 passed in 2.83s ==========================
```

## GREEN — production workflow restored

The workflow catch block was restored to the merged #1128 content before this run.

Command:

```console
$ python3 -m pytest tests/test_gate_commit_status_fork_tolerance.py -q
collected 8 items

tests/test_gate_commit_status_fork_tolerance.py ........                 [100%]

============================== 8 passed in 2.43s ===============================
```

The named gate therefore fails when fork tolerance is removed and passes when the
merged fix is present.
