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
$ printf 'PYTEST_ADDOPTS=%s\n' "${PYTEST_ADDOPTS-<unset>}"
PYTEST_ADDOPTS=<unset>
$ python3 -m pytest tests/test_gate_commit_status_fork_tolerance.py -q
============================= test session starts ==============================
platform darwin -- Python 3.12.2, pytest-9.1.1, pluggy-1.6.0
rootdir: /private/tmp/counter-risk-evidence.nRvYDT
configfile: pyproject.toml
plugins: langsmith-0.10.9, cov-7.1.0, xdist-3.8.0, rerunfailures-16.3, datadir-1.8.0, typeguard-4.5.1, asyncio-1.3.0, pytest_httpserver-1.1.3, hypothesis-6.155.7, regressions-2.11.0, Faker-40.39.0, anyio-4.13.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 8 items

tests/test_gate_commit_status_fork_tolerance.py FFFF....                 [100%]

=================================== FAILURES ===================================
________________ test_fork_read_only_403_does_not_fail_the_gate ________________

outcomes = {'fork_read_only': {'warnings': [], 'summaryWrites': 0, 'summaryRaw': [], 'threw': {'status': 403, 'message': 'Resource not accessible by integration'}}, ...}

    def test_fork_read_only_403_does_not_fail_the_gate(outcomes: dict[str, Any]) -> None:
>       assert outcomes["fork_read_only"]["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:174: AssertionError
_______________ test_fork_read_only_403_reports_the_real_verdict _______________

outcomes = {'fork_read_only': {'warnings': [], 'summaryWrites': 0, 'summaryRaw': [], 'threw': {'status': 403, 'message': 'Resource not accessible by integration'}}, ...}

    def test_fork_read_only_403_reports_the_real_verdict(outcomes: dict[str, Any]) -> None:
        case = outcomes["fork_read_only"]
        warning = " ".join(case["warnings"])
        summary = " ".join(case["summaryRaw"])
>       assert "read-only" in warning
E       AssertionError: assert 'read-only' in ''

tests/test_gate_commit_status_fork_tolerance.py:181: AssertionError
______________ test_fork_read_only_403_preserves_failure_verdict _______________

outcomes = {'fork_read_only': {'warnings': [], 'summaryWrites': 0, 'summaryRaw': [], 'threw': {'status': 403, 'message': 'Resource not accessible by integration'}}, ...}

    def test_fork_read_only_403_preserves_failure_verdict(
        outcomes: dict[str, Any],
    ) -> None:
        case = outcomes["fork_read_only_failure"]
        warning = " ".join(case["warnings"])
        summary = " ".join(case["summaryRaw"])
>       assert case["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:195: AssertionError
_____________ test_deleted_fork_read_only_403_reports_the_verdict ______________

outcomes = {'fork_read_only': {'warnings': [], 'summaryWrites': 0, 'summaryRaw': [], 'threw': {'status': 403, 'message': 'Resource not accessible by integration'}}, ...}

    def test_deleted_fork_read_only_403_reports_the_verdict(
        outcomes: dict[str, Any],
    ) -> None:
        case = outcomes["deleted_fork_read_only"]
        warning = " ".join(case["warnings"])
>       assert case["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:205: AssertionError
=========================== short test summary info ============================
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_does_not_fail_the_gate
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_reports_the_real_verdict
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_preserves_failure_verdict
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_deleted_fork_read_only_403_reports_the_verdict
========================= 4 failed, 4 passed in 0.41s ==========================
```

## GREEN — production workflow restored

The workflow catch block was restored to the merged #1128 content before this run.

Command:

```console
$ python3 -m pytest tests/test_gate_commit_status_fork_tolerance.py -q
collected 8 items

tests/test_gate_commit_status_fork_tolerance.py ........                 [100%]

============================== 8 passed in 0.33s ===============================
```

The named gate therefore fails when fork tolerance is removed and passes when the
merged fix is present.
