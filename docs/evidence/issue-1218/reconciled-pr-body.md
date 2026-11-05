## Summary

Continue existing PR **#1232** on `codex/issue-1218`; no additional PR or production changes. Reconcile the earlier work, then strengthen the next ranked target, `compute/rollups.py`, with two repo-cash alias regression cases. Citibank and Citigroup must accumulate into one counterparty row whether the first adjustment creates the row or matches existing row zero. Signed adjustments must update Cash, both notional aliases, and both change aliases exactly once.

Reviewed recent commits `5090e30`, `4c08e8b`, `ab025f3`, and `b9b5e18`, plus the earlier ranked-target evidence. Commit `5090e30` already delivered the NISA dimensionless-workbook EOF case, its mutation receipts, and mechanical Black formatting. The earlier local publication-blocker report is historical; automation subsequently committed those files.

## Coverage and baseline reconciliation

The issue cited **89.32% blended line+branch**. Repository configuration now measures **lines only** (`branch=false`), and PR Gate runs disable coverage. Use whole-suite coverage for target comparisons, not a single test file's subset. Historical matched Python 3.12 runs against original issue base `faad152` recorded **10,911/12,216 (89.3173%) → 11,109/12,216 (90.9381%)**, **198 fewer missing statements**, exceeding the original ~180 goal by 18. Those gains already exist on current main and are not an incremental claim for this follow-up.

Existing Python 3.14 evidence before this round: **3,054 passed, 1 skipped**, **11,722/12,232 (95.8306%)**. Fresh whole-suite verification with the two added cases: **3,056 passed, 1 skipped**, **11,722/12,232 (95.8306%)**, 116.82 seconds. This existing delivery already exceeds 90%; the new tests add behavioral discrimination and claim **zero additional covered statements**. No extra PR, threshold change, or manufactured production fix is needed.

| Target, in issue order | Historical missing before | Current missing | Historical before % | Current whole-suite % |
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

Seven defensive statements remain: two NISA inference fallbacks whose public caller supplies nonempty numeric headers; one CLI empty-payload fallback after an unconditional append loop; two runtime empty-catalog fallbacks where configuration supplies defaults; and two repeated provider missing-environment checks after the condition already raised. These are the documented partial targets; no padding tests bypass public invariants to reach them. The original chunk's 198-statement reduction and these explanations satisfy the documented partial-delivery alternative, not a claim of a new Gate coverage measurement.

## Verification and break-and-revert

- Whole suite: `python -m pytest tests/ -m "not slow" -n 4 --dist load --cov=counter_risk --cov-report=term-missing --cov-report=json:/tmp/issue-1218-rollups-whole-after.json -q` → **3,056 passed, 1 skipped**; rollups' table row is **311 statements, 0 missing, 100%**.
- Targeted: `python -m pytest tests/compute/ -m "not slow" --cov=counter_risk.compute.rollups --cov-report=term-missing --cov-report=json:/tmp/issue-1218-rollups-after.json -q` → **388 passed**, rollups **99%** (three DataFrame output-column filler statements exercised by tests outside this subset). The whole-suite 100% figure is authoritative.
- Fresh verification of prior NISA work plus existing rollup tests at `5090e30`: **100 passed**, NISA **216/218, 99%**. A single `test_rollups.py` run measured only 80%, illustrating why subsets cannot replace the whole-suite baseline.
- Black **26.10.1**: exact requested `black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .` and the reusable CI variant adding `\.venv` both passed, **414 files unchanged**. Commands used `BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/issue-1218-black-cache`. Initial multi-file invocations stalled; serial Black checks verified all 414 files before the successful repository-wide checks. No source formatting edits were needed this round.
- Ruff **0.17.3**: `ruff check --output-format github --extend-exclude .workflows-lib .` passed. Flags confirmed from the local Workflows reusable CI source; no workflow files changed.

For **each of the two new parametrized cases**, ran `python -m pytest tests/compute/test_rollups.py::test_repo_cash_accumulates_aliases_into_one_counterparty -m "not slow" -q`, adding `--junitxml=<report>` for machine-readable outcomes:

| Deliberate production break | Broken run | Restored run |
|---|---|---|
| Bypass normalization of incoming overlay aliases | 2 failed, exit 1 | 2 passed, exit 0 |
| Treat matched index zero as absent (`if not matched_index`) | 2 failed, exit 1 | 2 passed, exit 0 |
| Replace signed amount with its absolute value | 2 failed, exit 1 | 2 passed, exit 0 |

Receipt: `docs/evidence/issue-1218/rollups-alias-mutation-receipts.json`, including commands, assertion failures, outcomes for both cases, and matching source SHA-256 before/after. Production source was restored byte-for-byte after every mutation. No real bug was exposed by these new cases.

The prior NISA EOF case's two truncation mutations each produced **1 failed, 1 passed**; restoration produced **2 passed** (`eof-mutation-receipts.json`). Prior alias-order cases produced **2 failed** with the original alias order and **2 passed** restored (`notional-alias-mutation-receipt.json`). Other earlier scenarios retain their committed receipts under this evidence directory.

## Production fix rationale and hosted verification

The original chunk's only production fix put specific `notional_change` aliases before generic `notional`. Previously, a change column left of Notional was consumed by the generic substring match and caused a valid workbook to fail header validation. Two real-XLSX regression cases demonstrated the bug and its minimal fix. This round changes tests and evidence only.

Independently verified Gate run [41983898851](https://github.com/stranske/Counter_Risk/actions/runs/41983898851) at existing head **`5090e306e2899189cc473b8b223f4de2afe61593`**: Python **3.13 and 3.14** pytest jobs succeeded; Ruff and mypy succeeded; the hosted format job was skipped. That run verifies the prior NISA EOF change, not these new local rollup tests. Hosted verification of this round remains pending publication.

## Reconciled task checklist

- [x] Reconcile recent commits and distinguish whole-suite, subset, historical, and current coverage.
- [x] Run repository formatter and linter with the requested and reusable CI flags on changed files; both repository-wide checks pass.
- [ ] Deliver this round's verified changes as a committed, pushed update to existing PR #1232; publication is blocked below.
- [ ] Cover NISA fully: 28 of the 30 historical missing statements covered; two public-contract fallbacks documented above.
- [x] Cover rollups: all 16 historical missing statements covered; current whole-suite 100%; two new alias cases pass mutation proof.
- [x] Cover runner_launch: current whole-suite 100%.
- [ ] Cover CLI mapping_diff_report fully: one unreachable fallback documented above.
- [x] Cover reports/mapping_diff: current whole-suite 100%.
- [ ] Cover langchain_runtime fully: two unreachable fallbacks documented above.
- [x] Cover normalize: current whole-suite 100%.
- [x] Cover limits_config: current whole-suite 100%.
- [ ] Cover provider base fully: two repeated checks documented above.
- [x] Cover pptx_postprocess: current whole-suite 100%.
- [x] Cover build/xlsm: current whole-suite 100%.
- [x] Run actual break-and-revert for both new cases; earlier additions retain their receipts.
- [x] Keep production changes limited to the original demonstrated alias bug; no new production changes.
- [x] Keep one existing ready-for-review PR, #1232, with issue closer and per-target before/after evidence.
- [ ] CI verifies this round's new tests; existing head passed hosted Python 3.13 and 3.14.
- [x] Document original ~180-unit goal, historical 198-statement reduction, current zero incremental gain, and every partial target.
- [x] Follow the issue's ranked order, preserve low blast radius, and add no thresholds, exclusions, dependencies, or workflow changes.

## Publication blocker

Automatic approval review rejected the PR-body reconciliation: **MCP tool call requires approval, but approval policy is never**. This file is the concrete replacement body prepared locally; its checked boxes have not been applied to the live PR. Local `git add` failed (exit 128): `.git/index.lock` cannot be created because `.git` is read-only. No commit or push was made. An apply-ready patch including the new test and mutation receipt is saved at `/tmp/issue-1218-rollups-verified.patch`. The live PR was confirmed open and ready for review; the remaining work is publication and hosted verification of this local test change.

Closes #1218
