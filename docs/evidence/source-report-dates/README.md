# Source report-date ambiguity regression

The scope regression in `tests/test_dates.py::test_malformed_additional_date_cannot_confirm_source_period`
checks that a valid leading date followed by a malformed additional date cannot
confirm a match or mismatch. It also preserves configured-date precedence and
the legacy fallback selection.

For the deliberate-break gate, temporarily change the token-counting line in
`src/counter_risk/dates.py::source_report_date_evidence` from
`tokens = _DATE_TOKEN_PATTERN.findall(value_text)` to
`tokens = _REPORT_DATE_TOKEN_PATTERN.findall(value_text)`. This disconnects the
safeguard by discarding malformed additional tokens before counting them.

Command for both runs:

```sh
python -m pytest tests/test_dates.py -k malformed_additional_date -m "not slow" -q
```

- [Disconnected safeguard](malformed-date-disconnected.txt): exit 1, four failures
  because the sources were incorrectly classified `identified`.
- [Restored safeguard](malformed-date-restored.txt): exit 0, four passes.

The source was restored in a `finally` block and its contents checked against the
pre-mutation implementation. Subsequent verification passed all 61 tests in
`tests/test_dates.py`, `tests/pipeline/test_as_of_header_mismatch.py`, and
`tests/pipeline/test_header_extraction_boundaries.py` with `-m "not slow"`.
