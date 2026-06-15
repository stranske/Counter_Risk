# Counter_Risk — Whole-App Audit

## Executive Summary

Counter_Risk is a well-engineered pipeline: the code is clean (ruff passes, ~1350 tests collected), strongly typed, and disciplined about failing loudly rather than miscomputing. Config loading uses `extra="forbid"` so typo'd keys are caught, parsers raise typed exceptions on missing sheets/headers, and the pipeline wraps every stage with consistent error handling and provenance/manifest validation. However, the app is **not ready for the intended no-install Windows operator path**, and there are **four genuinely wrong-number / wrong-outcome defects** that affect the risk report itself.

The two highest-impact correctness bugs are: (1) `percent_of_total` limit checks divide by a denominator that mixes counterparty-totals and futures rows, so clearing-house/segment/custom-group concentration limits are silently diluted and real breaches can fail to trigger (`compute/limits.py:195` + `pipeline/run.py:2206-2254`); and (2) HHI/Top-N concentration math is mathematically invalid for mixed-sign (short) notionals, empirically returning HHI=19801 (`compute/rollups.py:576-586`). On the Windows side, the frozen `.exe` **crashes during reconciliation** because `name_registry.yml` is resolved via a source-tree path (`parents[3]`) that does not exist in the bundle (`pipeline/reconciliation.py:23`), `limit_breaches.csv` is silently dropped for the same reason, and the headline PowerPoint deliverable cannot be produced because `pywin32` is in no dependency manifest.

Two operator-facing safety/UX gaps compound this: a configured **`severity:fail` limit breach never escalates the data-quality status to RED** and never fails the run (`pipeline/data_quality.py:20`, `manifest.py:117-123`), and the shipped `Runner.xlsm`'s "buttons" are inert cell text with no controls wired to the VBA macros, so a non-technical operator cannot trigger anything. The tkinter GUI is the more operator-ready surface but freezes on the main thread during a run and surfaces raw exit codes instead of the operator-friendly messages the repo already implements.

**Verdict: usable today only from a real Python environment (dev/maintainer setup). NOT ready for the no-install Windows operator flow, and the limit/concentration defects should be fixed before the numbers are trusted for distribution.** With the BLOCKERs addressed (frozen-path resolution, percent-of-total denominator, HHI sign handling, fail-breach escalation, XLSM buttons) it becomes a solid with-caveats local tool.

## Scorecard

| Dimension | Grade | One-line |
|-----------|-------|----------|
| Code Quality | B+ | Clean, typed, fails loudly; marred by mixed-sign HHI bug and a dead/buggy shadow `pipeline.py` module |
| Calc Correctness | C+ | Correct for non-negative notionals; HHI wrong for shorts; NaN can leak silently into WAL |
| Functionality & Wiring | C | Most params correctly wired; `percent_of_total` denominator defect dilutes concentration limits |
| Parsers | B | Defensive and loud; UTF-8 BOM bug breaks the normal Windows CSV path; FCM uses fragile fixed column indices |
| Pipeline / Orchestration | B+ | Disciplined stage handling and manifest hygiene; fail-breach never escalates to RED |
| Duplication | B- | Two byte-identical XLSX readers and ~4 drifting numeric coercers (a correctness risk), otherwise well-factored |
| Design / Ease of Use | C | GUI usable but freezes & shows raw errors; XLSM buttons are inert text |
| Windows Readiness | D | Frozen exe crashes in reconciliation; no pywin32 for PPT; unsigned + UPX-packed; no operator doc |

## 1. Code Quality

Overall quality is high and consistent. Strengths span the codebase: division-by-zero is guarded everywhere it matters (`wal.py:31`, `rollups.py:355,579`, `limits.py:219`); `futures_delta._extract_notional` is exemplary (explicit None/blank/non-numeric/NaN handling with structured warning codes); the manifest layer validates schema before any disk write (`manifest.py:185-205`) and rejects unsafe artifact paths (`manifest.py:523-545`); COM is correctly gated behind `sys.platform`/`find_spec` with graceful non-Windows fallbacks; and `renderers/table_png.py` ships a pure-Python PNG encoder for byte-stable screenshots.

Concrete code-quality defects:

- **[BLOCKER] HHI / Top-N wrong for mixed-sign notionals.** `compute/rollups.py:576-586` sorts raw notionals and computes `hhi = sum((n/total)**2)`. With short positions in scope (`top_exposures` and `check_limits` both use `abs()`), notionals 100 and -99 yield HHI=19801 and Top5/Top10 mis-rank (a large negative exposure sorts to the bottom). Fix: rank/weight by `abs(notional)` over `sum(abs(...))`, with a near-zero-total guard. This is the single inconsistency that the duplicated/diverging helpers (below) made easy to introduce.
- **[MAJOR] Sign/`abs` convention is inconsistent across one package** — `rollups.py:384` uses `-abs(...)`, `rollups.py:576` uses the raw value, `limits.py:195,210` use `abs(...)`. Centralize the magnitude convention.
- **[MAJOR] Silent NaN propagation into WAL.** `parsers/exposure_maturity_schedule.py:96-99` `_coerce_float` returns `float(value)` without a NaN check; a `float('nan')` cell flows into `calculate_wal`, whose `total_exposure == 0` guard (`wal.py:31`) does not catch NaN, so WAL silently becomes `nan`. Reject/zero NaN, or guard with `math.isfinite`.
- **[MAJOR] Dead, stale, buggy shadow module `src/counter_risk/pipeline.py`** is shadowed by the `pipeline/` package and never imported, but contains a copy of `run_fixture_replay` missing the `if source_path is None: continue` guard (live version `fixture_replay.py:63-64`) — it would raise `FileNotFoundError`. Delete it.
- **[MAJOR] Production reconciliation mutates another module's globals for test injection** — `reconcile_series_coverage` (`run.py:120-144`) overwrites `reconciliation.normalize_counterparty_with_source` per call; it is a no-op in production (same object) and not thread-safe. Use dependency injection instead.
- **[MAJOR] `as_of_date` accepted by MOSERS writers and silently discarded** (`writers/mosers_workbook.py:74-89`, `_ = as_of_date`) while the pipeline passes a real value (`run.py:1522-1526`). The API lies to its caller; drop the param or stamp the date.
- **[MAJOR] CPRS-FCM uses hard-coded column indices** (`cprs_fcm.py:143-167,198-218`) instead of CPRS-CH's header map — any layout drift silently maps wrong cells to TIPS/Treasury/Notional with no error.
- **[MINOR]** WAL `px_date` parameter is coerced then never used (`wal.py:16,26`); dead `OutputContext.warnings` channel (`outputs/base.py:22`); fixed `13` first-data-row in `historical_update._append_to_sheet` (`:559-560`) vs correct `header_row+1` elsewhere; US-only number-locale assumptions silently corrupt European decimals; `%` stripped but not rescaled by /100 in several coercers; non-standard JSON-Schema enum with `None` member (`manifest_schema.py:378`).

## 2. Duplication & Simplification

Most of the codebase is appropriately factored (outputs Protocol+registry, historical_update layering, ppt/ modules, the NISA "variant" files are thin intentional re-export shims — not duplication). Two clusters are worth acting on, the second being a correctness risk:

- **[MAJOR] Hand-rolled raw-XLSX reader duplicated near byte-for-byte** between `parsers/cprs_ch.py` and `parsers/cprs_fcm.py` (`_XML_NS`, `_load_shared_strings`, `_read_sheet_rows`, `_cell_value`, `_column_index_from_reference`; compare `cprs_ch.py:465-539` with `cprs_fcm.py:328-401`). ~110 lines, low refactor risk. Extract `parsers/_xlsx_reader.py` with a sheet-selection predicate.
- **[MAJOR] "Accounting string → float" coercer in ~4 drifting copies** — `cprs_ch._extract_numeric` (`:405`), `cprs_fcm._extract_numeric` (`:414`), `nisa._coerce_float` (`:190`), `exposure_maturity._coerce_float` (`:95`), plus `daily_holdings_pdf._parse_amount` and `chat/session.py`. They disagree on `%` stripping (exposure does not strip it), paren-negatives, and range validation (only cprs_ch enforces `abs > 1e15`). This is the same drift that produced the WAL NaN gap and the HHI sign inconsistency. Consolidate into one `coerce_accounting_float(...)`.
- **[MINOR]** Three near-identical YAML load+validate+error-format scaffolds (`config.py:170-199`, `limits_config.py:89-120`, `name_registry.py:150-179`) — only `limits_config` rejects duplicate keys; consolidating into one `load_yaml_model(...)` helper would fix that inconsistency for free. Duplicated apostrophe/dash regexes (`name_matching.py:8-11` vs `normalize.py:29-32`); four near-identical `open_*` functions in `runner_launch.py:259-440`; command/argv construction mirrored in `gui/runner.py` and `runner_launch.py`; repeated openpyxl import guard and COM open/close try/finally scaffolding.

## 3. Functionality & Parameter Wiring

Most parameters are correctly loaded, validated, and move outputs in the economically correct direction (verified by spot-check): `limit_value` tightening produces breaches for both `absolute_notional` and `percent_of_total`; `enabled:false` excludes entries; `strict_missing_entities:true` raises; `series_included`/`by_segment` inclusion has correct precedence; `reconciliation.fail_policy:strict` raises. Config loaders are strict.

- **[BLOCKER] `percent_of_total` limits diluted by a mixed-granularity denominator.** `compute/limits.py:195` computes one global `total_abs_notional = sum(abs(notional))` over a row set that `pipeline/run.py:2206-2254` (`_build_limit_exposure_rows`) builds by concatenating counterparty-totals rows and futures-dimension rows. A `clearing_house` cap (shipped `cme` 0.35) divides CME futures notional by *all counterparty totals plus all futures* — spot-check: CME=40 of 100 futures but with 1000 of counterparty totals computes 40/1100 = 3.6% instead of 40%, so a real 40% concentration does not breach the 35% limit. Same dilution hits `segment`/`custom_group`; counterparty limits are inversely distorted. Not caught by tests (only homogeneous row sets are exercised). Fix: scope the denominator to the same `entity_type`/granularity.
- **[BLOCKER] `severity:fail` limit breach never turns the data-quality summary RED.** `data_quality.py:20` maps `LIMIT_BREACHES` to `"warn"` unconditionally and `build_data_quality` ignores the `fail_breach_count`/`max_severity` the pipeline already computes (`run.py:2295-2299`, forwarded via `manifest.py:117-123`). A hard limit breach yields `overall_status="warn"` → YELLOW "Review warnings before sending" instead of RED "Do not send." For a distribution tool this is a safety gap. Emit a `fail`-severity finding when `fail_breach_count > 0`.
- **[MAJOR] `severity:fail` also does not halt the run / exit nonzero** — it is reported (CSV, manifest, GUI banner) but the run completes successfully, asymmetric with `strict_missing_entities` and reconciliation `fail_policy:strict`, both of which raise.
- **[MINOR]** `WorkflowConfig.enable_llm_logging` (`config.py:118`) is never read — dead. `custom_group` futures limits only match if the parser emits that column (shipped entry is `enabled:false`, so no current impact). `cash_total_min` has no standalone validation.

## 4. Design, Ease of Use & Windows Readiness

The tkinter GUI is the more operator-ready of the two surfaces — coherent single window, constrained dropdowns, auto-defaulted month-end date, plain-language data-quality labels, graceful tkinter-unavailable fallback, and a tested `--headless` mode. But it has real gaps, and the Windows no-install path is broken.

- **[BLOCKER] Frozen `.exe` crashes during reconciliation.** `pipeline/reconciliation.py:23` resolves `name_registry.yml` via `Path(__file__).resolve().parents[3] / "config" / ...`; in a frozen bundle `parents[3]` points outside the bundle root, `load_name_registry()` raises, and the run aborts before outputs complete — the exact path the worker `.cmd` exercises. Route through `resolve_runtime_path(...)` and add a frozen-mode test.
- **[BLOCKER] Runner.xlsm "buttons" are inert text.** A5:I5 are plain `inlineStr` cells; the package has no `drawing`/`legacyDrawing`/`control`/`oleObject` parts, so nothing invokes the existing `RunAll_Click` etc. macros. A non-technical operator cannot trigger anything (only Alt+F8 by name). Also "Ask about this run" (I5) has no handler, and the shipped workbook omits the `Config` file-path sheet the VBA reads (`RunnerLaunch.bas:639-654`).
- **[BLOCKER] GUI "discover" mode calls `input()` on stdin** (`io/discover.py:242` via `gui/runner.py:149-150`); in a windowed `.exe` there is no stdin, `input()` raises `EOFError` → `SystemExit(1)`, which the GUI's `except Exception` does not catch, so the whole app exits silently on any multi-match. Pass a Tk selection dialog or disable discover in the windowed GUI.
- **[MAJOR] Limit breaches silently dropped in frozen build** — `run.py:2265` resolves `limits.yml` via the same `parents[3]`; the guard returns no CSV, so `limit_breaches.csv` just disappears (INFO log only).
- **[MAJOR] PowerPoint deliverable unobtainable from the no-install bundle** — `pywin32`/`win32com` is in no manifest (`requirements*.txt`, `pyproject.toml`); the headline "screenshots replaced + links refreshed" deck cannot be produced; the operator gets an un-refreshed deck plus `NEEDS_LINK_REFRESH.txt`. Decide/document the supported model or add `pywin32`.
- **[MAJOR] GUI runs the full pipeline synchronously on the Tk main thread** (`gui/runner.py:292-321`) — window goes "Not Responding" for minutes; no cancel, no progress. Move to a worker thread + `root.after`.
- **[MAJOR] GUI surfaces raw exit codes/exceptions** ("Exit code 1") instead of the operator-friendly `format_launch_error_for_runner`/`map_runner_error_to_operator_message` the repo already implements (`runner_launch.py:46-83`). Wire it in. Also "Open ..." buttons (`runner.py:323-339`) have no try/except and silently no-op on a malformed date.
- **[MAJOR] Unsigned + UPX-packed exe** (`release.spec:49,55,65`) → SmartScreen/AV friction with no operator guidance. Disable UPX for the operator build, add an Authenticode signing step, document "Run anyway".
- **[BLOCKER → parser] UTF-8 BOM breaks CSV ingestion on the normal Windows path.** `repo_cash_sources.py:186` opens CSVs with `encoding="utf-8"` not `utf-8-sig`; Excel "CSV UTF-8" exports prepend a BOM that attaches to the first header, so `load_repo_cash_overrides_csv` raises "missing required columns: counterparty." Open with `utf-8-sig`.
- **[MINOR]** No operator-facing Windows run doc (only CI/keepalive `SETUP_CHECKLIST.md` and the auto-generated bundle README); default `runs/` output resolves to the bundle parent in frozen mode; frozen tkinter GUI unverified on Windows; jargon field labels with no help text; fixed `640x380` geometry can clip; XLSM run is hidden+synchronous with even less feedback than the GUI.

## Prioritized Action List

| # | Severity | Item | Area | Effort |
|---|----------|------|------|--------|
| 1 | BLOCKER | Frozen exe crashes in reconciliation — route `name_registry.yml`/`limits.yml` (and bare `Path("config/...")` defaults) through `resolve_runtime_path`; add frozen-mode test (`reconciliation.py:23`, `run.py:2265`) | Windows | M |
| 2 | BLOCKER | `percent_of_total` denominator mixes granularities — scope denominator per `entity_type` (`compute/limits.py:195`, `run.py:2206-2254`) | Functionality | M |
| 3 | BLOCKER | `severity:fail` breach never escalates to RED — emit fail-severity finding (`data_quality.py:20`, `manifest.py:117-123`) | Pipeline | S |
| 4 | BLOCKER | HHI/Top-N wrong for mixed-sign notionals — rank/weight by `abs()`, add near-zero-total guard (`rollups.py:576-586`) | Calc | M |
| 5 | BLOCKER | UTF-8 BOM breaks Windows CSV ingest — open with `utf-8-sig` (`repo_cash_sources.py:186`) | Parsers | S |
| 6 | BLOCKER | Runner.xlsm buttons are inert text — attach Form Controls to `*_Click` macros, ship `Config` sheet, resolve "Ask about this run" | Design | M |
| 7 | BLOCKER | GUI discover mode `input()` exits app in windowed exe — Tk dialog or disable discover (`io/discover.py:242`, `gui/runner.py:149`) | UI | M |
| 8 | MAJOR | PPT deliverable needs Office+pywin32 — add `pywin32` or document the split model | Windows | M |
| 9 | MAJOR | GUI freezes on Tk main thread — run pipeline on worker thread + `root.after` | UI | M |
| 10 | MAJOR | GUI shows raw exit codes — wire `format_launch_error_for_runner`; wrap "Open ..." handlers | UI | S |
| 11 | MAJOR | Unsigned + UPX-packed exe — `upx=False`, add signing, SmartScreen doc (`release.spec`) | Windows | M |
| 12 | MAJOR | Silent NaN into WAL — reject NaN in `_coerce_float` / guard with `isfinite` (`exposure_maturity_schedule.py:96`, `wal.py:31`) | Calc | S |
| 13 | MAJOR | `severity:fail` does not halt/exit-nonzero — align with strict knobs | Functionality | S |
| 14 | MAJOR | CPRS-FCM hard-coded column indices — switch to header map (`cprs_fcm.py:143-218`) | Parsers | M |
| 15 | MAJOR | Delete dead/buggy shadow `src/counter_risk/pipeline.py` | Code Quality | S |
| 16 | MAJOR | Reconciliation mutates module globals for tests — use DI (`run.py:120-144`) | Pipeline | S |
| 17 | MAJOR | `as_of_date` accepted and discarded by MOSERS writers — drop or honor (`mosers_workbook.py:74`) | Outputs | S |
| 18 | MAJOR | Extract shared XLSX reader (`cprs_ch.py:465-539` / `cprs_fcm.py:328-401`) | Duplication | M |
| 19 | MAJOR | Consolidate ~4 drifting accounting-float coercers into one helper | Duplication | M |
| 20 | MAJOR | GUI: no file pickers / path validation for roots | Design | M |
| 21 | MINOR | Centralize sign/`abs` convention; reject inf in `_find_numeric` | Calc | S |
| 22 | MINOR | Inconsistent YAML duplicate-key handling — shared `load_yaml_model` | io-config | M |
| 23 | MINOR | Screenshot replacement misleading geometry-mismatch error; brittle EMU tuples (`pptx_screenshots.py:154-169`) | Outputs | S |
| 24 | MINOR | Operator-facing Windows run doc; sensible default `runs/` in frozen mode | Windows | M |
| 25 | MINOR | Remove dead symbols: `enable_llm_logging`, `OutputContext.warnings`, `_normalize_whitespace`, `_OPTIONAL_INPUTS`, WAL `px_date` | Code Quality | S |
| 26 | MINOR | `historical_update._append_to_sheet` fixed row 13 vs `header_row+1` (`:559-560`) | Outputs | S |
| 27 | MINOR | Document US-only number-locale assumption / `%` rescale contract | Parsers | S |

## Test & Lint Baseline

Baseline facts verified by the orchestrator on macOS:

- **Lint:** `ruff check src/counter_risk` → **All checks passed.**
- **Imports:** package imports cleanly.
- **Tests:** **1350 tests collected.** A full `pytest` run was launched separately and was still in progress at synthesis time — the audit artifact `docs/audit/_test_run.txt` is present but empty (0 bytes), so no pass/fail counts are available to incorporate. The audit findings are based on source review, not on a recorded test-failure list.

Note: several BLOCKER/MAJOR defects above are explicitly **not covered by the existing test suite** and would pass a green run — the `percent_of_total` denominator bug (only homogeneous row sets are tested), the mixed-sign HHI bug, the fail-breach→RED escalation gap, and frozen-mode path resolution (`tests/unit/test_runtime_paths.py` covers the helper but not the reconciliation/limits call sites). Adding targeted regression tests for these should accompany the fixes.
