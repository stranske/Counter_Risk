## Summary

Expand regression coverage across issue #1218's ranked targets in escaped-defect, churn, then uncovered-mass order. Earlier verified work reduced uncovered target statements by 198. This follow-up continues with the first ranked target, `parsers/nisa.py`, and fixes a real header-alias bug with two regression cases.

When a workbook places `Notional Change` or `Notional Change From Prior Month` before `Notional`, the generic `notional` substring used to capture the change column. The parser then rejected the valid workbook as missing required headers. Match the existing specific `notional_change` aliases before the generic `notional` alias. This is the only production change; it reorders existing entries and adds an explanatory comment. No refactor, dependency, workflow, coverage exclusion, or threshold changes.

The two real-XLSX cases assert counterparties and distinct notional/change values in both CH and totals. Both failed on the original production code. An explicit break-and-revert run restored the original alias order: **2 failed**, pytest exit 1; exact fixed-source restoration: **2 passed**, exit 0. `notional-alias-mutation-receipt.json` records the command, per-case outcomes, full outputs, and matching fixed/restored SHA-256 hashes.

## Coverage

The repository's configuration uses line-only coverage (`branch = false`); no blended line+branch improvement is claimed. Gate disables coverage, so the measurements below are matched local whole non-slow suite results, not a Gate coverage artifact. The original base baseline was below 90%; this is a continuation of the same existing PR.

- Base `faad152`: 10,911/12,216 statements, **89.3173%**, agreeing with the issue's rounded 89.32% baseline.
- Current candidate: 11,109/12,216 statements, **90.9381%**; **198 fewer uncovered statements** in ranked targets, exceeding the approximate 180-unit goal by 18.
- This follow-up changes behavior and adds regression discrimination; it claims **zero additional covered statements** over the earlier candidate.
- Focused NISA coverage: **36 passed**, actual coverage table **99%**, 216/218 statements covered; only defensive lines 240/312 remain missing.

| Target, in issue order | Missing before | Missing after | Coverage before | Coverage after |
|---|---:|---:|---:|---:|
| parsers/nisa.py | 30 | 2 | 86.24% | 99.08% |
| compute/rollups.py | 16 | 0 | 94.86% | 100% |
| runner_launch.py | 14 | 0 | 92.75% | 100% |
| cli/mapping_diff_report.py | 12 | 1 | 87.76% | 98.98% |
| reports/mapping_diff.py | 12 | 0 | 87.88% | 100% |
| chat/providers/langchain_runtime.py | 9 | 2 | 96.17% | 99.15% |
| normalize.py | 5 | 0 | 95.54% | 100% |
| limits_config.py | 3 | 0 | 94.74% | 100% |
| chat/providers/base.py | 2 | 2 | 98.77% | 98.77% |
| ppt/pptx_postprocess.py | 54 | 0 | 66.46% | 100% |
| build/xlsm.py | 48 | 0 | 60.33% | 100% |

Seven defensive statements remain across the ranked targets: NISA's public caller guarantees nonempty numeric headers before the two missing inference fallbacks; CLI's nonempty payload-path loop unconditionally appends loaded payloads; runtime configuration supplies default slots rather than an empty catalog; provider base repeats a missing-environment error after the same condition already raised. These were previously documented as unreachable through the public contracts. Their line numbers can move with comments; this follow-up does not bypass invariants to reach them.

## Validation

- `COVERAGE_FILE=/tmp/counter-risk-1218-alias-suite.coverage python -m pytest tests/ -m "not slow" -n 4 --dist load --cov=counter_risk --cov-report=term --cov-report=json:/tmp/counter-risk-1218-alias-suite.json -q`: **2,571 passed, 1 skipped** in 125.72 seconds. Coverage JSON confirms 11,109/12,216 statements.
- `COVERAGE_FILE=/tmp/counter-risk-1218-alias-target.coverage python -m pytest tests/test_nisa_all_programs_parser.py -m "not slow" --cov=counter_risk.parsers.nisa --cov-report=term-missing -q`: **36 passed**, **99%**.
- Black 26.10.1 formatted both changed Python files at line length 100. Required check `black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .` and CI check adding `\.venv` to the exclusion both passed: **395 files unchanged**. As in earlier rounds, a temporary startup shim schedules asyncio wakeups and `BLACK_NUM_WORKERS=1` accommodates the sandbox; formatting and parse validation remain enabled.
- CI Ruff 0.17.3: `ruff check --output-format github --extend-exclude .workflows-lib .` passed.
- `git diff --check` passed.

Earlier break-and-revert receipts remain in `docs/evidence/issue-1218/`: `mutation-receipts.json`, `numeric-mutation-receipts.json`, `sheet-selection-mutation-receipts.json`, `segment-mutation-receipts.json`, and the completeness, cleanup, diagnostics, inference, segment-score, header-precedence, and stop-marker receipts. They record actual failing mutations and passing restored runs for previous additions. Hosted CI for this new candidate remains pending publication; previous heads' Gate results do not verify this source change.

## Verified contract tasks

1. [x] Pick the next target by the repo's own coverage-gap ranking: NISA is explicitly first in issue #1218.
2. [x] Run break-and-revert for each new test: both new alias cases failed with the original alias order and passed after exact restoration; the receipt includes individual outcomes.
3. [x] Fix real bugs with a minimal targeted diff: reordered the two overlapping header aliases after the tests demonstrated workbook rejection. No cache logic is involved.
4. [x] Low blast radius: two XLSX regression cases and a three-line production diff, with no refactor.
5. [x] One PR per logical chunk: continue existing PR #1220; no additional PR opened.

## Delivery status

The primary checkout's `.git` directory is read-only: `git add --dry-run` fails creating `index.lock`. The verified source, tests and evidence are preserved in the writable checkout `/tmp/counter-risk-1218-notional-alias`. The change is committed in that writable checkout and preserved in `/tmp/counter-risk-1218-notional-alias.bundle`. Git push failed with `Could not resolve host: github.com`. Automatic approval review rejected GitHub connector publication, the PR-body update, the blocker comment, and the `needs-human` label: `MCP tool call requires approval, but approval policy is never`. Consequently the live task checkboxes were not changed, and hosted CI for this candidate remains pending. PR #1220 was reverified open and ready for review (`isDraft=false`) at `c117a610df4ee03b59b5eaf60785ecaf63171846` after those attempts.

Closes #1218
