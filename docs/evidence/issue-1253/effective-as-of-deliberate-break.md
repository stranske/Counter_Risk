# Issue #1253 effective as-of deliberate-break evidence

Regression: `tests/pipeline/test_as_of_header_mismatch.py::test_inferred_as_of_mismatch_with_identified_sources_is_conflict`

Production behavior lives in `src/counter_risk/dates.py::compare_source_report_dates` (effective-date
conflicts when `configured_date` is unset).

## Procedure

1. Run the named pytest on unmodified branch `cursor/issue-1253` at HEAD.
2. Temporarily require `configured_date is not None` before comparing `effective_date` to identified
   source report dates (omits effective-date comparisons when config is unset).
3. Re-run the identical pytest command; capture the expected failure (`has_conflict` becomes false).
4. Restore production handling and re-run; capture pass.
5. Record literal transcripts below.

Executed on branch `cursor/issue-1253` with Python 3.14.10 (keepalive 2026-11-17 UTC, round 1256 re-verify).

## RED — effective comparisons omitted when config unset

Temporary mutation in `src/counter_risk/dates.py`:

```diff
     effective_conflicts = [
         entry["variant"]
         for entry in identified
-        if effective_date is not None and entry["report_date"] != effective_date.isoformat()
+        if (
+            configured_date is not None
+            and effective_date is not None
+            and entry["report_date"] != effective_date.isoformat()
+        )
     ]
```

Command:

```console
$ python3 -m pytest tests/pipeline/test_as_of_header_mismatch.py::test_inferred_as_of_mismatch_with_identified_sources_is_conflict -q
```

Result (exit code 1): **FAILED** — full transcript in `effective-date-disconnected.txt`.

```text
FAILED tests/pipeline/test_as_of_header_mismatch.py::test_inferred_as_of_mismatch_with_identified_sources_is_conflict - assert False is True
```

March 1 header inference versus January 31 sources no longer raises `has_conflict` when
`configured_date` is null.

## GREEN — production handling restored

Command:

```console
$ python3 -m pytest tests/pipeline/test_as_of_header_mismatch.py::test_inferred_as_of_mismatch_with_identified_sources_is_conflict -q
```

Result (exit code 0): **1 passed** — transcript in `effective-date-restored.txt`.

Production source bytes restored unchanged after the deliberate break.

<!-- deliberate-break: test=tests/pipeline/test_as_of_header_mismatch.py::test_inferred_as_of_mismatch_with_identified_sources_is_conflict test-file=tests/pipeline/test_as_of_header_mismatch.py break-file=src/counter_risk/dates.py -->