# Issue 1140 starting threshold measurement

Fresh starting measurement at `6d0e77a524337b38383967a1dfb200b951db771c`, before any new source or test changes:

```sh
python -m pytest -q -n 4 -m "not release and not slow" --cov=counter_risk --cov-report=json:coverage.json
```

Python 3.14.8, Linux, four workers: **2,225 passed, 1 skipped in 549.65s**; collection confirms 48 release/slow deselections. Exact package line coverage: **10,841 / 12,038 = 90.05648778866922%**, with 1,197 missing lines and 84 excluded lines. This exceeds the 90% stopping threshold without relying on rounding.

The refreshed last-500-source-commit repair-history proxy/churn/uncovered-line ranking still selects `pipeline/run.py` first (19 repair-subject matches, 111 source commits, 301 missing lines). Repair history is a disclosed subject proxy, not a verified incident count. All 66 focused header/fallback/directory acceptance cases pass on Python 3.14.8; the 20 existing header-evidence hashes match. Python 3.12 cannot rerun pytest here because pytest is not installed for that interpreter.

Raw package coverage JSON, full console output, collection, complete history and ranking, focused output and hashes are retained locally in `docs/evidence/issue-1140-threshold-check/`. The established Python 3.12 baseline/candidate and eight mutation receipts remain in `docs/evidence/issue-1140-header-extraction/`.

Applying this issue's explicit >=90% stop rule: no new source/test changes or additional PR are warranted. Existing PR #1144 remains open and ready for review at the measured head; its merge/verifier disposition is separate. The measurement omits release/slow tests and does not establish branch, Office, native or hosted integration coverage.

Only the measurement/ranking task is newly verified. The conditional stop rule supersedes further regression work for this run. GitHub delivery status is recorded in `delivery.json`; evidence in this folder is local until committed or attached by an authorized runner.

Verified progress for this run:

- [x] Measure the package with the required full command and rank production gaps.
- [ ] Post the measured evidence and close #1140: both writes were rejected because approval is required while approval policy is `never`. The `needs-human` label was rejected for the same reason.

No additional source/tests, candidate run, commit or PR were created: the measured starting coverage triggers the task's explicit stopping exception. #1140 remains open; #1144 remains open with `draft=false` and the unchanged measured head. An authorized runner must post `closing-comment.md` and close #1140.
