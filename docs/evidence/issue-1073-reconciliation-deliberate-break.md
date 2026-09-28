# Issue #1073 CPRS-CH reconciliation deliberate-break evidence

This evidence closes the transcript gap tracked by issue #1125 for merged PR
#1124. The regression lives in `tests/pipeline/test_reconciliation.py`, and the
production finite-value guard lives in
`src/counter_risk/pipeline/run.py::_extract_mosers_program_notional_from_cprs_ch`.

## Procedure

1. Run the focused invalid-workbook regression on the unmodified source.
2. Remove only the `math.isfinite(notional)` rejection from the production
   workbook extractor.
3. Run the identical focused command and capture the expected failure.
4. Restore the exact guard and rerun the identical command.
5. Run the full reconciliation test module with coverage enabled.

Executed from commit `af156e8` on branch
`codex/issue-1125-deliberate-break-evidence` with Python 3.12.2.

## RED — finite-value guard deliberately removed

Temporary mutation:

```diff
-                if not math.isfinite(notional):
-                    raise ValueError("non-finite notional")
```

Command:

```console
$ uv run pytest tests/pipeline/test_reconciliation.py -k invalid_workbook -q
collected 24 items / 18 deselected / 6 selected

tests/pipeline/test_reconciliation.py ..FFF.                             [100%]

=================================== FAILURES ===================================
___ test_invalid_workbook_notional_fails_cprs_ch_totals_reconciliation[nan] ____
E       AssertionError: assert 'MOSERS Program row' in 'CPRS-CH totals check failed: non-finite CPRS-CH MOSERS program notional'

___ test_invalid_workbook_notional_fails_cprs_ch_totals_reconciliation[inf] ____
E       AssertionError: assert 'MOSERS Program row' in 'CPRS-CH totals check failed: non-finite CPRS-CH MOSERS program notional'

___ test_invalid_workbook_notional_fails_cprs_ch_totals_reconciliation[-inf] ___
E       AssertionError: assert 'MOSERS Program row' in 'CPRS-CH totals check failed: non-finite CPRS-CH MOSERS program notional'

=========================== short test summary info ============================
FAILED tests/pipeline/test_reconciliation.py::test_invalid_workbook_notional_fails_cprs_ch_totals_reconciliation[nan]
FAILED tests/pipeline/test_reconciliation.py::test_invalid_workbook_notional_fails_cprs_ch_totals_reconciliation[inf]
FAILED tests/pipeline/test_reconciliation.py::test_invalid_workbook_notional_fails_cprs_ch_totals_reconciliation[-inf]
================== 3 failed, 3 passed, 18 deselected in 0.71s ==================
```

The finite-value guard is therefore coupled to the named invalid-workbook
regression rather than passing vacuously.

## GREEN — exact guard restored

The two removed lines were restored exactly before this run.

```console
$ uv run pytest tests/pipeline/test_reconciliation.py -k invalid_workbook -q
collected 24 items / 18 deselected / 6 selected

tests/pipeline/test_reconciliation.py ......                             [100%]

======================= 6 passed, 18 deselected in 0.65s =======================
```

## Full reconciliation validation

```console
$ uv run pytest tests/pipeline/test_reconciliation.py --cov=counter_risk.pipeline.run --cov-report=term-missing -q
collected 24 items

tests/pipeline/test_reconciliation.py ........................           [100%]

Name                               Stmts   Miss  Cover
------------------------------------------------------
src/counter_risk/pipeline/run.py    2508   2188    13%
------------------------------------------------------
TOTAL                               2508   2188    13%
============================== 24 passed in 1.07s ==============================
```

The coverage percentage is expected for this focused reconciliation module: the
command records exercised production lines and does not impose a repository-wide
coverage threshold.
