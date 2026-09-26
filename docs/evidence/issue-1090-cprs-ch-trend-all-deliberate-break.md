# Deliberate-break evidence: CPRS-CH trend filename guard (#1090 / #1103)

Linked issue: `stranske/Counter_Risk#1110` (D4 verification follow-up for merged PR #1103 / issue #1090).

## Mutation (temporary, not committed)

In `src/counter_risk/parsers/cprs_ch.py`, the variant guard was temporarily reverted to treat any
filename containing `"all"` as `all_programs`, removing the `"trend" not in title` exemption that
#1103 restored.

Production code on this branch keeps the merged fix; this file records the RED/GREEN transcript only.

## RED — old `"all" in title` precedence, then

`pytest tests/parsers/test_cprs_ch.py::test_parse_cprs_ch_trend_workbook_not_misclassified_when_filename_contains_all -q --no-cov`

```
FAILED tests/parsers/test_cprs_ch.py::test_parse_cprs_ch_trend_workbook_not_misclassified_when_filename_contains_all[mosers-trend-all.xlsx]
FAILED tests/parsers/test_cprs_ch.py::test_parse_cprs_ch_trend_workbook_not_misclassified_when_filename_contains_all[small-trend.xlsx]
FAILED tests/parsers/test_cprs_ch.py::test_parse_cprs_ch_trend_workbook_not_misclassified_when_filename_contains_all[trend-allocation.xlsx]
============================== 3 failed in 3.94s ===============================
```

Representative failure: trend workbooks were classified as `all_programs`, raising
`ValueError: Missing expected CPRS-CH segments: futures_cdx, repo, swaps`.

## GREEN — restored guard, same command

```
============================== 3 passed in 6.87s ===============================
```

## Verification command (this PR)

`pytest tests/parsers/test_cprs_ch.py::test_parse_cprs_ch_trend_workbook_not_misclassified_when_filename_contains_all -q --no-cov`

Recorded on branch tip after sync with `origin/main` (2026-09-26).
