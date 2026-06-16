# Counter_Risk audit-fix implementation — summary

Branch: **`audit-fixes`** → PR https://github.com/stranske/Counter_Risk/pull/732. Base: `main`.

**All 27 audit items now implemented** (the 3 initially-deferred MINORs were completed in a follow-up
once the name-registry regression was understood — see below).

## Test & lint state (final)

- Broad suite (`-m "not slow and not release"`, parallel): **1,329 passed, 1 failed, 1 skipped**.
- The 1 failure — `tests/test_pptx_replacement_workflow.py::test_replacement_workflow_near_match_slide_remains_unchanged`
  — **also fails on `main`** (image-hash mismatch; environment-dependent rendering on macOS/Pillow). It is
  **pre-existing**, not introduced by these changes.
- `ruff check src/counter_risk` → **All checks passed.**
- The heavyweight `slow`/`release` tests were verified piecewise per lane, not in this broad run.

## Commits

| Commit | Audit items | What |
|--------|-------------|------|
| `cc8b73c` | #1 | Frozen-build config resolution via `resolve_runtime_path` |
| `3dd714b` | #2,3,4,13,15,16,21 | HHI abs-weighting; per-granularity `percent_of_total` denominator; fail-breach → RED + run halt; reconciliation DI; delete dead `pipeline.py`; centralize sign convention |
| `929cb04` | #5,12,14,18,19,27 | utf-8-sig BOM; NaN→WAL guard; CPRS-FCM header map; shared `_xlsx_reader`; consolidated `coerce_accounting_float` |
| `d2b4c1d` | #8,11,24-doc | pywin32 win32 marker; UPX off + Authenticode/SmartScreen note; Windows operator runbook |
| `0f091cb` | #7,9,10,17,20,23,26 | GUI worker-thread + path pickers + friendly errors; discover `input()` fix; honor `as_of_date`; pptx geometry; historical append-row |
| `90ab43e` | #6 | Runner.xlsm Form Control buttons wired to existing VBA macros (vbaProject.bin untouched) + Config sheet |
| `f482538` | (regression fix) | Reconciliation name_registry resolves to absolute repo path in source mode; lint |

## BLOCKERs: all 7 addressed

Items: #1 frozen-config · #2 denominator · #3 fail→RED · #4 HHI · #6 xlsm buttons · #7 GUI-crash · #13 fail→halt

## Follow-up: previously-deferred MINORs (now done) — commit `2bab544`

- **#22** unify YAML loaders into `counter_risk.yaml_utils.load_yaml_model` (config/limits/name-registry).
  Initially reverted because it appeared to break 5 limit tests — but that was a **confound**: the failures
  were the name-registry CWD bug (`f482538`), not the loader. With that fixed, the shared loader applies
  cleanly and now gives consistent duplicate-key rejection across all three configs (added regression tests).
- **#24** `output_root` defaults via `resolve_default_output_root` (next to the exe when frozen).
- **#25** removed dead `WorkflowConfig.enable_llm_logging`.

## Verification notes / caveats

- **#6 Runner.xlsm**: verified valid OOXML, `openpyxl.load_workbook(keep_vba=True)` succeeds, `vbaProject.bin` byte-identical, 45 runner/VBA tests pass. Two labels ("Dry-Run Discovery", "Ask about this run") have no existing VBA handler so get no button. **Final click-test requires opening in desktop Excel on Windows** (cannot be verified from macOS/headless).
- **#17 as_of_date** stamped to `CPRS - CH` A3/B3 in the MOSERS workbook.
- The `_resolve_repo_root` / `resolve_runtime_path` source-vs-frozen split is subtle: source mode must use absolute repo-tree paths (the pipeline chdirs into run folders). See `f482538`.

## How this was built

Orchestrated across local agents (codex = correctness core; gemini = parsers/dedup; claude = packaging;
cursor = UI; codex = xlsm), each in scoped lanes, verified independently before commit. UI + xlsm lanes ran in an
isolated git worktree (`/tmp/cr-audit-work`) to immunize against the machine's autonomous agent fleet, which twice
switched the main checkout's branch during long test waits.
