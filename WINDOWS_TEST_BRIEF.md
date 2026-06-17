# Windows test brief — Counter_Risk (branch `audit-fixes`, PR #732)

> For an agent running on the **Windows PC**. This branch implemented the audit fixes (see
> `docs/audit/IMPLEMENTATION_SUMMARY.md`). Most was verified on macOS, but a few items are
> **Windows/Excel-only** and need you to confirm them. Do these, record results, and report back.

## 0. Setup
```powershell
# from the repo root, on branch audit-fixes
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pip install -e .
```
Use `.\.venv\Scripts\python` for every command below.

## 1. Full test suite (incl. the tests skipped on macOS)
The macOS run excluded `slow`/`release` markers and hit one environment-dependent failure. On Windows run **everything**:
```powershell
.\.venv\Scripts\python -m pytest -q
```
- **Expected:** all pass. **Report any failure** with the test id + short traceback.
- **Specifically check** `tests/test_pptx_replacement_workflow.py::test_replacement_workflow_near_match_slide_remains_unchanged`
  — it fails on macOS with an *image-hash* mismatch (same geometry, different bytes), suspected to be a
  Pillow/font rendering difference. If it **passes** on Windows, say so. If it **fails**, paste the two hashes;
  do **not** rebaseline without confirmation.

## 2. Runner.xlsm — clickable buttons (audit #6, the key unverified item)
Open `Runner.xlsm` in desktop Excel (Enable Macros / Content):
- Confirm the **Runner** sheet shows clickable **Form Control buttons** over row 5: Run All, Run Ex Trend,
  Run Trend, Dry-Run Discovery, Open Output Folder, Open Manifest, Open Summary, Open PPT Folder.
  ("Dry-Run Discovery" and "Ask about this run" intentionally have **no** button — no VBA handler exists.)
- Confirm there is a **Config** sheet.
- Click **Run All** (with valid inputs/paths set per the workbook): confirm it launches the pipeline and writes a
  run folder, rather than erroring. Click an **Open …** button: confirm it opens the right folder/file.
- **Report:** do the buttons exist, fire the bound macro, and complete without a VBA error? Screenshot if possible.

## 3. Frozen executable + GUI (audit #1, #7, #9, #10, #20, #24)
Build and run the operator `.exe`:
```powershell
.\.venv\Scripts\pyinstaller release.spec
.\dist\counter-risk\counter-risk.exe gui
```
Confirm, in the GUI:
- It launches (no missing-DLL/tkinter error) and the window **stays responsive during a run** (runs off the UI thread).
- **Browse** buttons pick input/output folders; Run is disabled until paths are valid.
- A failing run shows a **plain-language error**, not a raw "Exit code 1".
- A run **completes end-to-end and writes a run folder** — this exercises the frozen-path fix (#1): the bundled
  `config\name_registry.yml` / `limits.yml` must resolve (no "No such file" error), and `runs\` should land
  **next to the .exe** (#24).
- **Report:** launches? responsive? run completes? where did output land?

## 4. PowerPoint generation via COM (audit #8 — pywin32, needs Excel+PowerPoint installed)
The headline deck (screenshots replaced + chart links refreshed) uses `win32com` and only works on Windows w/ Office.
Run a normal monthly cycle (GUI or `counter-risk run --config <your.yml>`) with PPT output enabled and confirm the
`.pptx` is produced/refreshed without a `pywin32`/COM import error. **Report** success or the exact error.

## 5. UTF-8 BOM CSV ingest (audit #5)
In Excel, save a repo-cash overrides CSV as **"CSV UTF-8 (Comma delimited)"** (which adds a BOM), point the config
at it, and confirm it loads (no "missing required columns: counterparty"). **Report** pass/fail.

## How to report
Reply with a short checklist: section number → PASS / FAIL (+ error text or screenshot). Flag anything that needs a
code change so it can be fixed on the PR before merge. If §2 or §3 fail, that's a blocker for the operator workflow.
