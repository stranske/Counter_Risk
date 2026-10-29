# Root-discovery follow-up verification

Environment: Python 3.14.9, pytest 9.2.0, Black 26.10.1, Ruff 0.17.3.

Reviewed the three recent commits (`ba3969a`, `4af5ae2`, `c80d63c`) and the previous validation evidence before adding tests. The live PR description still describes only the initial schema tests, although the commits cover all eight ranked targets. The five unchecked contract tasks are verified by the existing evidence plus this follow-up. Their reconciled checkboxes are in [pr-body.md](pr-body.md); the remote update was rejected.

The next reachable gap after the completed schema target and documented serializer fallbacks is historical workbook root discovery. The earlier test replaced the root-discovery helper itself. Two new parametrized cases exercise that helper through `open_ex_llc_3_year_workbook()`, selecting the workbook beside a simulated module location even when the current directory contains a valid decoy. Both preferred and legacy directory layouts are tested. No production bug was found.

- Before changes: writer tests with targeted `--cov=counter_risk.writers.historical_update`: **119 passed, 5 deselected**, 93% coverage. This narrower suite is not the CI baseline.
- New boundary suite: **29 passed**, using `-m "not slow"`.
- Actual mutation: replace `return Path(__file__).resolve().parents[3]` with `return Path.cwd()`. Both new cases fail at the returned workbook path assertion: **2 failed**. Restore the original bytes and rerun: **2 passed**. Exact output is in [root-discovery-mutation-transcript.txt](root-discovery-mutation-transcript.txt).
- Full non-slow suite with targeted coverage for all eight ranked modules: **2624 passed, 1 skipped**, in 74.93 seconds. Command and coverage table are in [root-discovery-coverage-transcript.txt](root-discovery-coverage-transcript.txt).
- The coverage table shows `historical_update.py`: **360 statements, 5 missed, 99%**. Previous whole-suite evidence had 6 missed. Total local improvement from `faad152`: **177 covered lines**, 13 remaining, three short of the 180-unit aim. The issue/Gate baseline remains authoritative; this is not a repository-wide 90% claim.
- `git diff --exit-code -- src`: passed after source restoration.
- `ruff check --output-format github --extend-exclude .workflows-lib .`: passed.
- `git diff --check`: passed.

## Formatting gate

Formatted the changed test file with `black --line-length 100 tests/writers/test_historical_update_boundaries.py`: unchanged.

The initial single-worker whole-repository Black invocation stalled and was interrupted (exit 130). A bounded verbose diagnostic timed out (exit 124). Neither was counted as a successful gate. A sequential Black check using its normal `reformat_one` API reported all 401 tracked Python files unchanged and populated its normal cache in `/tmp/1216-followup-black-cache`. No formatter configuration, security setting, or cache contents were manually altered.

Both subsequent direct commands exited 0 and reported **401 files would be left unchanged**:

```sh
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/1216-followup-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/1216-followup-black-cache black --check --line-length 100 --exclude '(\.venv|\.workflows-lib|node_modules)' .
```

## Publication blockers

- Staging the meaningful test change failed: `fatal: Unable to create '/home/runner/work/Counter_Risk/Counter_Risk/.git/index.lock': Read-only file system`. This run cannot commit or push; no alternate Git-directory path was used.
- The authorized PR-body reconciliation tool returned: `MCP tool call requires approval, but approval policy is never`. No alternate API was used to bypass that rejection. The updated description and verified contract checkboxes remain in [pr-body.md](pr-body.md).
- Existing PR #1216 is open and ready for review (`isDraft=false`) at `c80d63c`. Its Gate run 40834166290 succeeded. The two new cases have local verification only and still require publication and CI.

Protected files were not changed. This follow-up consists of the two new test cases and verification evidence.
