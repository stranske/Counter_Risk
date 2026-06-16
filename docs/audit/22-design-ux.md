# 22 — Design & Ease of Use Audit: Local Operator Surfaces

Summary line: The tkinter GUI is the clearly more operator-ready surface; the shipped `Runner.xlsm` has labeled "buttons" that are inert cell text (no clickable controls wired to the VBA macros), which is a BLOCKER for a non-technical operator.

## Summary

Two local surfaces are intended for a non-technical operator who understands the *purpose* of the monthly counterparty-risk run: (a) the tkinter GUI (`src/counter_risk/gui/runner.py`, launched via `counter-risk gui`) and (b) `Runner.xlsm` driven by the `RunnerLaunch` VBA module. Both share the same underlying contract (settings JSON + CLI args + run-folder convention), so they are functionally close. The decisive difference is interaction wiring and discoverability.

The tkinter GUI is coherent end-to-end: form fields, dropdowns constrained to valid values, Run / Dry-Run buttons, post-run open buttons, and a Status/Result/Data-Quality/Limit-Breach readout. It has real usability gaps (no file picker, raw exit-code errors, a UI that freezes during the run, terse field labels), but it is genuinely usable.

`Runner.xlsm` is conceptually well designed (a validated month-end dropdown, a clean label-and-button layout, color-coded data-quality cell, sensible operator-facing error mapping in `runner_launch.py`), but the *shipped workbook is not wired up*: the "Run All / Run Ex Trend / … / Ask about this run" labels in row 5 are plain `inlineStr` cell values, not Form Control buttons, Shapes, or ActiveX controls. There are no `drawing`/`legacyDrawing`/`control`/`oleObject` parts in the package, so nothing invokes `RunAll_Click` etc. A non-technical operator cannot click anything; they would have to run macros by name via Alt+F8. The workbook is also missing the `Config` file-path sheet that the VBA reads.

Recommendation: ship the **tkinter GUI** as the primary local interface and treat `Runner.xlsm` as a fallback that must be rebuilt with real buttons before it is operator-facing.

## tkinter GUI Runner — usability & layout

Files: `src/counter_risk/gui/runner.py`, `src/counter_risk/runner_launch.py` (shared helpers), CLI wiring in `src/counter_risk/cli/__init__.py:121-256`, docs `docs/gui_runner.md`.

### What works well
- **Single coherent window.** `launch_gui` (runner.py:247) builds a 640x380 window titled "Counter Risk Runner" with seven labeled form rows, two action buttons, four open buttons, and four readout labels. The flow top-to-bottom (configure → Run → inspect results → open outputs) is intuitive.
- **Constrained inputs prevent error.** Mode, Discovery Mode, and Strict Policy are `readonly` Comboboxes (runner.py:353-373) with exactly the valid values, so an operator cannot mistype `all`/`ex_trend`/`trend`, `manual`/`discover`, or `warn`/`strict`.
- **Date is auto-defaulted to the current month-end.** `default_as_of_date` is computed via `parse_as_of_month(date.today())` (runner.py:259), so the field is pre-filled correctly for the common case.
- **Status feedback is legible.** After a run, Status/Result/Data Quality/Limit Breach labels update (runner.py:304-315). Data-quality maps to friendly labels like "GREEN - Safe to send" / "RED - Do not send" via `data_quality_status_label` (`runner_launch.py:443-469`), which is exactly the kind of plain-language guidance a non-technical operator needs.
- **Post-run affordances.** Open Output Folder / Manifest / Summary / PPT Folder (runner.py:390-401) cross-platform-open the right artifacts via `_open_path` (runner.py:204-212). They fall back to `resolve_existing_output_dir` when no run has happened yet, so they degrade gracefully.

### MAJOR issues
1. **[MAJOR] UI freezes for the entire run; no progress indication.** `_run` sets Status to "Running..." then calls `execute_gui_run` synchronously on the Tk main thread (runner.py:296-303). A real monthly run (PDF/XLSX ingest + Excel/PPTX generation) takes many seconds to minutes, during which the window is unresponsive and may show the OS "Not Responding" state. A non-technical operator will reasonably assume it crashed and may force-quit. There is no spinner, no progress, no disabled-button state. This is the single biggest usability defect of the GUI.
2. **[MAJOR] Errors surface as raw exit codes / exception text.** On non-zero exit, Result shows `f"Exit code {result.exit_code}"` (runner.py:313); on exception it shows `str(exc)` plus a generic `messagebox.showerror` (runner.py:316-321). The repo already has excellent operator-facing translation (`map_runner_error_to_operator_message`, `format_launch_error_for_runner` in `runner_launch.py:46-83`) that turns "input validation"/"unmatched counterparty"/"reconciliation strict mode failed" into actionable guidance — but the GUI never calls it. The operator-friendly messaging exists and is simply not wired into the GUI.
3. **[MAJOR] No file pickers / no path validation for roots.** Input Root and Output Root are free-text Entry widgets (runner.py:374-381) with no Browse button and no existence check. A non-technical operator must hand-type a path correctly. There is also no GUI surface for the seven source-file paths (MOSERS All Programs, Ex-Trend, Trend, the three histories, the PPTX template) that the xlsm path supports via `RunnerConfig_*` named ranges — the GUI can only rely on `config/*.yml` defaults plus discovery.

### MINOR issues
4. **[MINOR] Field labels are jargon without help text.** "Discovery Mode", "Strict Policy", "Formatting Profile", "Input Root", "Output Root" (runner.py:342-350) carry no tooltip, hint, or inline description. An operator who understands the *business* purpose still won't know what "Strict Policy: warn vs strict" does to their run. `docs/gui_runner.md` lists the fields but offers no explanation of each.
5. **[MINOR] "As-Of Date (YYYY-MM-DD)" is free text, unlike the xlsm.** The xlsm constrains the date to a validated month-end dropdown (ControlData list); the GUI accepts any ISO date and silently snaps it to month-end via `parse_as_of_month`. A bad format raises and dumps the exception into Result/messagebox rather than guiding the operator. A date picker or month dropdown would match the xlsm's safer design (and `runner_date_control.py` already documents month-selector as the chosen control for non-technical operators).
6. **[MINOR] Fixed `640x380` geometry can clip.** With 15 grid rows of labels/buttons/readouts, longer status/result strings (e.g. a full error message or a limit-breach banner) wrap or truncate in a non-resizable-feeling small window. Only column 1 is weighted (runner.py:383); rows are not, so the readout area does not grow.
7. **[MINOR] No "what will run" confirmation.** Clicking Run immediately executes against real inputs and writes a real run folder. There is no preview of the resolved command/output dir, and Dry-Run Discovery is a separate button an operator may not understand to use first.

## Runner.xlsm — usability & layout

Files: `Runner.xlsm` (sheets `Runner`, `ControlData` hidden, `Settings`), VBA in `assets/vba/RunnerLaunch.bas`, build/injection in `src/counter_risk/build/xlsm.py`, maintainer setup `scripts/windows/setup_config_sheet.ps1`.

### Intended design (good on paper)
- **Clean single landing sheet.** `Runner` sheet: A1 title "Counter Risk Runner", A2 instruction "Select reporting month-end date and choose a run mode.", A3 "As-Of Month" with the input in B3, a row of action labels in A5:I5 ("Run All", "Run Ex Trend", "Run Trend", "Dry-Run Discovery", "Open Output Folder", "Open Manifest", "Open Summary", "Open PPT Folder", "Ask about this run"), and a Status/Result/Data-Quality readout block (A7:B9).
- **Excellent date control.** B3 has a `dataValidation type="list"` bound to `ControlData!$A$2:$A$193` — a precomputed list of month-end dates 2020-01-31 … 2035-12-31. This is exactly the deterministic, cross-Office-reliable month selector that `runner_date_control.py:43-67` reasons toward for a non-technical operator. Much safer than the GUI's free-text date.
- **Color-coded data quality.** `WriteDataQualityStatusCell` (RunnerLaunch.bas:591-609) writes "GREEN - Safe to send" / "YELLOW - Review warnings" / "RED - Do not send" with matching cell fill colors. This is the single best at-a-glance signal of either surface.
- **Operator-facing error semantics exist.** The Python mirror `format_launch_error_for_runner` / `map_runner_error_to_operator_message` (`runner_launch.py:46-83`) provides "Operator action: …" guidance; the VBA writes "Error N: …" to the Result cell.
- **Settings sheet is editable and labeled.** `Settings` sheet has labeled rows (Input Root, Discovery Mode, Strict Policy, Formatting Profile, Output Root) with named ranges, so an operator can adjust without touching JSON.

### BLOCKER / MAJOR issues
1. **[BLOCKER] The "buttons" are not buttons.** In `xl/worksheets/sheet1.xml`, A5:I5 are plain `t="inlineStr"` text cells. The package contains **no** `drawing`, `legacyDrawing`, `control`, or `oleObject` parts (confirmed in the zip member list: only `vbaProject.bin` plus styles/sheets). The VBA handlers `RunAll_Click`, `RunExTrend_Click`, `RunTrend_Click`, `OpenOutputFolder_Click`, etc. exist in `vbaProject.bin` but nothing in the workbook invokes them. A non-technical operator who clicks "Run All" gets a selected cell, not a run. The only way to trigger a run is Alt+F8 → pick the macro by name — which defeats the entire purpose of the surface. This must be fixed (assign Form Control buttons or Shapes to each `*_Click` macro) before `Runner.xlsm` can be considered operator-ready.
2. **[BLOCKER] "Ask about this run" has no handler.** The label exists in I5 but there is no corresponding macro (string scan of `vbaProject.bin` shows `RunAll`/`OpenOutput`/etc. but no `AskAbout`). Even after wiring buttons, this affordance is dead.
3. **[MAJOR] Shipped workbook is missing the `Config` file-path sheet that the VBA depends on.** `BuildSettingsJson` (RunnerLaunch.bas:639-654) reads seven `RunnerConfig_*` named ranges (MOSERS All Programs / Ex-Trend / Trend, three histories, monthly PPTX). The shipped `Runner.xlsm` has only `Runner`, `ControlData`, `Settings` and only the five `RunnerSetting_*` names — no `Config` sheet and no `RunnerConfig_*` names. `ReadSettingValue` falls back to "" so it is not a crash, but the documented file-path override feature is silently unavailable, and the workbook diverges from `inject_config_sheet` (`build/xlsm.py:138-204`). An operator following any doc that references the Config sheet will not find it.
4. **[MAJOR] Setup is a maintainer-only, fragile COM dance.** `setup_config_sheet.ps1` requires Excel installed, "Trust access to the VBA project object model" enabled, and re-injecting the `.bas`. The whole macro path also depends on macros being enabled past Excel's Mark-of-the-Web/Protected-View block, plus a built `dist\counter-risk.exe` discoverable at `ThisWorkbook.Path\dist\` (`ResolveExecutablePath`, RunnerLaunch.bas:427-429). Many corporate environments disable VBA macros entirely — which is the stated reason the GUI exists ("macro-restricted environments", runner.py:1). For those operators the xlsm is a non-starter.

### MINOR issues
5. **[MINOR] Run executes hidden and synchronous with no progress.** `ExecuteShellCommand` runs the exe with window style `0` (hidden) and `waitOnReturn=True` (RunnerLaunch.bas:439-444). Excel will appear frozen for the whole run with only a transient "Running…/Finished" in B7. Same freeze problem as the GUI, with even less feedback.
6. **[MINOR] No on-sheet legend for modes/settings.** The sheet does not explain what Ex-Trend vs Trend vs All means, or what the Settings values do — same jargon gap as the GUI.

## Recommended Primary Surface

**Primary: the tkinter GUI (`counter-risk gui`).** Reasons:
- It is actually interactive today — buttons invoke runs; the xlsm's buttons do not (BLOCKER above).
- It works in macro-restricted environments, which is the explicit reason it was built (runner.py:1, `docs/gui_runner.md`).
- It ships with the PyInstaller bundle (`docs/gui_runner.md` install steps), so an operator with no Python/Excel/macro setup can run it; the xlsm requires Excel + enabled VBA + a maintainer-run PowerShell COM step.
- It already has a headless mode for CI smoke (`--headless`, cli/__init__.py:177-182), so the wiring is test-covered.

**Keep `Runner.xlsm` only as a documented fallback**, and do not present it to operators until (1) real Form Control buttons are attached to the `*_Click` macros, (2) the `Ask about this run` handler is implemented or the label removed, and (3) the shipped workbook is rebuilt to include the `Config` sheet via `inject_config_sheet`. The xlsm's *design* (validated month dropdown, color-coded DQ cell, editable Settings sheet) is in several respects better than the GUI's and should inform GUI improvements.

One caveat for picking the GUI: before it is the official primary surface, fix the run-thread freeze (MAJOR #1) and wire the existing operator-error translation (MAJOR #2), or first impressions on a long run will read as "it hung."

## Quick UX Wins

GUI (highest leverage first):
1. Run the pipeline off the Tk main thread (worker thread + `root.after` to post results); disable Run during execution and show a progress/"Running… this can take a few minutes" indicator. (runner.py:292-321)
2. Wire the existing `format_launch_error_for_runner` / `map_runner_error_to_operator_message` (`runner_launch.py:46-83`) into the error path so Result shows "Operator action: …" instead of "Exit code 1". (runner.py:311-321)
3. Add "Browse…" buttons + existence checks for Input Root / Output Root; consider a file picker for the seven source paths to reach parity with the xlsm Config sheet. (runner.py:374-381)
4. Replace the free-text As-Of Date with a month-end dropdown (reuse the `ControlData` month list / `runner_date_control.py` decision). (runner.py:343, 267)
5. Add one-line tooltips/help labels for Mode, Discovery Mode, Strict Policy, Formatting Profile. (runner.py:342-350)
6. Make the window resizable / weight the readout rows so long status and limit-breach text is fully visible. (runner.py:266, 383)

Runner.xlsm (only if it stays a supported surface):
7. Attach Form Control buttons (or Shapes with `OnAction`) to all eight `*_Click` macros so the labels are clickable. (Runner sheet A5:H5)
8. Implement or remove the `Ask about this run` action (I5).
9. Rebuild the shipped `Runner.xlsm` from the template after `inject_config_sheet` so the `Config` sheet and `RunnerConfig_*` named ranges are present. (`build/xlsm.py:138-204`)
10. Add a brief on-sheet note that macros must be enabled and `dist\counter-risk.exe` must exist alongside the workbook. (RunnerLaunch.bas:427-429)
