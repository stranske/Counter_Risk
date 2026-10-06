# Workbook header extraction: issue #1140

One test-only chunk on baseline `9a0e9f877a1828be662c37a4a8c2e5cdb2d084f8`. The previous #1143 chunk was independently dispositioned at PR comment 6022379505. Six new nodes cover three input classes: three open real XLSX workbooks using openpyxl read-only readers, two raise an optional-import error before any file is opened, and the corrupt-archive node supplies non-XLSX bytes. They protect row/column bounds, missing or broken optional imports, corrupt archives, an empty sheet inventory, partial-read rejection, and closing readers on success and error. No production bug was reproduced; production source and coverage configuration are unchanged.

## Selection

Rank the last 500 production-source commits by the whole-word repair-subject proxy `fix|bug|repair|regression|correct`, then churn, then measured uncovered statements. This is a disclosed proxy, not a verified escaped-incident count. `pipeline/run.py` remains first. Its header helper is the selected bounded uncovered behavior.

| Source | Repair proxy | Churn | Missing statements |
|---|---:|---:|---:|
| `src/counter_risk/pipeline/run.py` | 19 | 111 | 317 |
| `src/counter_risk/writers/historical_update.py` | 8 | 39 | 36 |
| `src/counter_risk/build/release.py` | 6 | 23 | 17 |
| `src/counter_risk/compute/futures_delta.py` | 6 | 19 | 9 |
| `src/counter_risk/compute/rollups.py` | 5 | 15 | 16 |

## Same-scope package measurement

Both commands: `python3.12 -m pytest -q -n 4 -m 'not release and not slow' --cov=counter_risk --cov-report=json:<capture>`. Python 3.12.2 / macOS / four workers; 106 production files with identical statement counts; line coverage only. Baseline ran in the delivery worktree before new tests were collected. Candidate ran in the separate linked proof worktree with identical production bytes and the final new test file, so mutations could not contaminate either run. Complete console and per-file JSON are retained adjacent. The ranking and mutation scripts are preserved verbatim as `.py.txt` provenance records; their recorded paths identify the original execution environment.

| Measurement | Baseline | Candidate |
|---|---:|---:|
| Covered statements | 10826 | 10842 |
| Total statements | 12038 | 12038 |
| Exact coverage | 89.931882372487% | 90.064794816415% |

Net statement change: +16. Gained/lost line inventories are in `header-summary.json`; no rounded 90% claim. Release/slow, native Office, hosted LangSmith and branch coverage are outside this measurement. Source issue stays open through merge/verifier disposition and the remaining initiative scope.

## Actual negative controls

Eight separate production mutations each fail the named node, then pass after byte-identical restoration (complete node/output/exit/hash receipts retained). A combined private broken reference `0e363f61b749b22a88b89d1430f092e73d918163` makes all six new nodes fail. It is a local negative control only and was never pushed. Its complete `git show` is stored losslessly in `header-combined-broken.patch.json` under `git_show` so patch context whitespace survives archival. Source restoration SHA256: `10038a2a20f1a6167d0e6992bc212e89546169d0a7e524350a4b2574b983723b`.

The complete TestGen gate passes collection/import, non-regression, three reliability runs, covered-line delta (+29 for its focused selection) and per-node discrimination (6/6, hollow 0 / inconclusive 0). Its first invocation lacked the broken reference and failed the no-hollow precondition; `testgen-gate.json` retains that incomplete invocation. The corrected complete receipt is `testgen-gate-complete.json`. Final focused/adjacent selection including the exact optional-reader meta-test: 47 PASS. The initial package candidate had 2225 PASS / 1 FAIL because a top-level import in the new test prevented collection in the pre-existing optional-reader absence check. Moving that import into workbook helpers repaired test collection without adding a skip or changing production. The initial failed output/coverage are retained alongside the final full candidate. Eight source-mutation controls give independent behavioral evidence beyond coverage.

## Receivers

Matching keepalive owns fresh hosted checks/review after push. Reviewed Repo Merge Verify Closer owns exact expected/protected topology, unchanged head, full review-thread pagination, seven-minute floor, guarded merge and verifier disposition. Local source tests do not establish hosted checks or deployment.
