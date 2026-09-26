# Audit-fix implementation — progress & remaining work

> **Historical audit snapshot (superseded 2026-09-23):** The BLOCKER-class findings in this report were addressed on `main` in merged PRs #1081–#1090 and #1103–#1107. For the current core-function list and open gaps, see `docs/PRODUCT_CONTRACT.md` and GitHub issues — do not treat the narrative below as live operator state.

Branch: `audit-fixes` (local only, not pushed). Base: `main`.

## Committed & verified (durable)
| Commit | Lane | Audit items | Verification |
|--------|------|-------------|--------------|
| `cc8b73c` | frozen-config | #1 | 3/3 frozen-path tests pass |
| `3dd714b` | codex core | #2 denom, #3 fail→RED, #4 HHI sign, #13 fail→halt, #15 dead module, #16 DI, #21 sign | 5 limit tests pass in isolation; compute/pipeline targeted green |
| `929cb04` | gemini parsers | #5 BOM, #12 NaN→WAL, #14 FCM header-map, #18 XLSX reader, #19 coercer, #27 doc | agent self-report 65 passed/0 failed |
| `d2b4c1d` | claude packaging | #8 pywin32 marker, #11 UPX off+signing note, #24 operator runbook | 5 packaging tests pass |

All 7 audit BLOCKERs' **core logic** is in except the two UI/packaging BLOCKERs below (#6, #7).
Imports clean on the branch.

## NOT yet done (resolved on main — kept for history)

The rows below described pre-merge gaps; they are **resolved on `main`** as of 2026-09-23 (#1081–#1090, #1103–#1107). See `docs/PRODUCT_CONTRACT.md` for current work.

### Cursor UI/outputs lane (resolved on main)
- **#7 [BLOCKER]** discover `input()` — resolved (GUI uses worker thread / non-blocking discover).
- #9 [MAJOR] GUI pipeline on Tk main thread — resolved.
- #10 [MAJOR] GUI raw exit codes — resolved.
- #17 [MAJOR] `as_of_date` discarded by MOSERS writers — resolved.
- #20 [MAJOR] GUI file/dir pickers + path validation — resolved.
- #23 [MINOR] pptx geometry-mismatch error/EMU robustness — deferred to issues.
- #25 [MINOR] dead `OutputContext.warnings` — deferred to issues.
- #26 [MINOR] `historical_update._append_to_sheet` row 13 — resolved.

### Runner.xlsm (resolved on main)
- **#6 [BLOCKER]** inert "buttons" — resolved (Form Controls wired in shipped workbook).

### Deferred MINORs (dropped from claude lane to avoid a test-breaking refactor)
- #22 unify YAML loaders (reverted — broke 5 limit tests despite being byte-faithful; mechanism unresolved)
- #24 `output_root` frozen default (in `runtime_paths.resolve_default_output_root`)
- #25 remove `WorkflowConfig.enable_llm_logging`

## Still owed
- Full reconciled `pytest` run on the assembled branch (the slow suite has at least one hanging test — needs a per-test timeout; isolate before trusting a full-suite number).

## Environmental hazard
An autonomous agent fleet runs on this machine and, when the orchestrator heartbeat goes stale
(>15 min, e.g. during long test waits), its opener lane will grab branches in this checkout and
switch the working tree (it did this once with the #1 commit → `fix/frozen-config-resolution`).
Recovered with no loss. Mitigation: refresh heartbeat each working turn, or run remaining work in
an isolated git worktree.
