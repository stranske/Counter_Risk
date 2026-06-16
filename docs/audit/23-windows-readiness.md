# Audit 23 — Windows Local-Implementation Readiness

**Summary line:** A fresh Windows PC cannot today go from zero to a complete report
package without a dev toolchain. The PyInstaller bundle ships, but the frozen `.exe`
crashes during reconciliation because `name_registry.yml` is resolved via a
source-tree-relative path that does not exist in the frozen layout; limit-breach
output silently disappears for the same reason; and the headline deliverable
(PowerPoint with refreshed links / replaced screenshots) requires Office + `pywin32`
in a Python environment, neither of which the no-install bundle provides.

Severity tags: **[BLOCKER]** wrong/broken/unsafe · **[MAJOR]** notable gap · **[MINOR]** polish.

---

## Packaging & Bundling

The packaging machinery is reasonably complete and Windows-aware in several places:

- `release.spec` bundles `templates/` and `config/` as PyInstaller `datas`, lists
  `tkinter`, `tkinter.ttk`, and `counter_risk.gui.runner` as `hiddenimports`, and
  builds a `console=True` exe named `counter-risk` (release.spec:14-37, 40-57).
- `pyinstaller_runtime_hook.py` sets `COUNTER_RISK_BUNDLE_ROOT` to `sys._MEIPASS`
  (one-dir collect mode) so data files can be located at runtime.
- `runtime_paths.resolve_runtime_path()` correctly searches `COUNTER_RISK_BUNDLE_ROOT`,
  `sys._MEIPASS`, and the executable directory, and is used by the CLI default config,
  the GUI config resolution, and the chat slot config (cli/__init__.py:56,
  gui/runner.py:66-68, chat/providers/langchain_runtime.py:132).
- `src/counter_risk/build/release.py` assembles a full operator bundle: builds the
  runner XLSM, copies templates/config/fixtures, runs PyInstaller, emits
  `run_counter_risk.cmd`, copies the two remote `.cmd` scripts, and writes
  `README_HOW_TO_RUN.md` + `manifest.json`. The generated `run_counter_risk.cmd`
  correctly probes `bin\counter-risk.exe` then `bin\counter-risk` (release.py:145-166).

The break is that **not all runtime asset lookups go through `resolve_runtime_path`.**
Two pipeline modules resolve config files relative to the *source tree* layout, which
does not exist inside a frozen bundle:

- **[BLOCKER]** `src/counter_risk/pipeline/reconciliation.py:23` —
  `_NAME_REGISTRY_PATH = Path(__file__).resolve().parents[3] / "config" / "name_registry.yml"`.
  In source mode `parents[3]` is the repo root (verified: resolves to
  `/Users/teacher/src/Counter_Risk`). In a frozen one-dir build `__file__` is
  `<bundle>/counter_risk/pipeline/reconciliation.py`, so `parents[3]` points at the
  *parent of the bundle root*, where no `config/` exists. `load_name_registry()`
  raises `ValueError` on a missing file (name_registry.py:159-169 wraps `OSError`),
  and reconciliation calls it via `counterparty_included_for_variant(...,
  registry_path=_NAME_REGISTRY_PATH)` and `collect_mapping_diff_findings(_NAME_REGISTRY_PATH, ...)`
  (reconciliation.py:106, 147). Net effect: **a `run` invoked from the frozen `.exe`
  crashes during reconciliation** — i.e., the exact path the worker `.cmd` exercises.

- **[MAJOR]** `src/counter_risk/pipeline/run.py:2265` —
  `limits_path = _resolve_repo_root() / "config" / "limits.yml"`, where
  `_resolve_repo_root()` is `Path(__file__).resolve().parents[3]` (run.py:836-839).
  Same frozen-path problem, but here there is a graceful guard:
  `if not limits_path.exists(): ... return LimitBreachEvaluation(csv_path=None, ...)`
  (run.py:2266-2268). So in the frozen build limit-breach detection is **silently
  skipped** — a documented pipeline output (`limit_breaches.csv`) just disappears with
  only an INFO log. The same source-root assumption also drives the default `runs/`
  output root (run.py:818, 836-839); harmless when `--output-dir` is passed (the worker
  `.cmd` does pass it), but the GUI and any default-output invocation would write `runs/`
  next to the bundle parent rather than a sensible operator location.

- **[MINOR]** `name_registry.py:159`, `limits_config.py:98`, `normalize.py:25`,
  `demo_artifact.py:211`, `cli/mapping_diff_report.py:24` all default to a bare
  `Path("config/...")` (CWD-relative). These are only safe when the process CWD is the
  bundle root. The generated `run_counter_risk.cmd` does not `cd` into the bundle, so
  CWD is wherever the operator launched it — another reason to route every default
  through `resolve_runtime_path`.

There is no automated test exercising frozen-mode path resolution for these two
pipeline modules; `tests/unit/test_runtime_paths.py` covers the helper but not the
reconciliation/limits call sites, so the blocker is untested.

---

## Platform Landmines

- **[MAJOR] PowerPoint/Excel COM requires Office + `pywin32`, which the no-install
  bundle does not provide.** `pywin32` / `win32com` appears in *no* dependency manifest
  (`requirements.txt`, `requirements.lock`, `requirements-dev.lock`, `pyproject.toml` —
  only `colorama` is win32-gated). `integrations/powerpoint_com.py:153` explicitly
  checks `importlib.util.find_spec("win32com.client")` and raises
  `PowerPointComUnavailableError` when absent. Consequences for a frozen exe (which can
  never contain `win32com` since it is not a build dependency):
  - PDF export is skipped gracefully (pdf_export.py:54-66) — acceptable.
  - PPT chart-link refresh falls back to copying the deck + writing
    `NEEDS_LINK_REFRESH.txt` with manual instructions (powerpoint_com.py:246-257).
  - PPT screenshot replacement via COM (run.py:59, `export_ppt_slides_as_png_via_com`)
    cannot run.
  The README headline deliverable is "Updated monthly PowerPoint (screenshots replaced
  + chart links refreshed)" (README:13). The no-install frozen path **cannot produce
  that**; it produces an un-refreshed deck plus a manual-steps text file. To get the
  real deliverable the operator machine needs Microsoft Office *and* a Python env with
  `pywin32` — i.e., not no-install. This split (data/workbooks via exe; final PPT via
  Office+Python) is real but undocumented for operators.

- **[MAJOR] UPX compression is enabled** (`upx=True` in both `EXE` and `COLLECT`,
  release.spec:49, 65). UPX-packed executables are a frequent false-positive trigger for
  Windows Defender / SmartScreen and corporate AV, and UPX itself must be installed at
  build time or PyInstaller silently skips it (build inconsistency between maintainer
  machines). For a non-technical operator receiving an unsigned, UPX-packed exe over a
  share, SmartScreen "Windows protected your PC" prompts are likely.

- **[MAJOR] No code signing.** `codesign_identity=None` (release.spec:55) and there is
  no Authenticode/`signtool` step anywhere in `release.py` or the scripts. An unsigned
  exe delivered to a fresh Windows PC will hit SmartScreen; nothing in the docs tells the
  operator to "More info → Run anyway", and corporate policy may block it outright.

- **[MINOR] tkinter in the frozen build is plausibly OK but unverified on Windows.**
  The spec hidden-imports `tkinter`/`tkinter.ttk`, and the GUI imports them lazily inside
  the window function (gui/runner.py:253-254) with a `--headless` fallback documented in
  `docs/gui_runner.md`. PyInstaller normally bundles the Tcl/Tk DLLs automatically, but
  this has not been validated on Windows in-repo. If Tk DLLs are missing the GUI fails at
  launch with no operator-facing remediation beyond "use Runner.xlsm".

- **[MINOR] Paths with spaces.** The generated `run_counter_risk.cmd` and the two remote
  `.cmd` scripts mostly quote variables (`"%EXE_PATH%"`, `"!EXE!"`), which is good.
  However `process_counter_risk_remote.cmd` builds `--input-root` from `%SCRIPT_DIR%`
  default and JSON-escapes backslashes via `:\=\\` substitution; a bundle path containing
  spaces is quoted in the exe call but the per-request settings JSON path
  (`%TEMP%\counter-risk-runner-settings-!BASE!.json`) and `!BASE!` come from the request
  filename — generally safe, but untested with spaces in the share path.

- **[MINOR] No POSIX-hardcoded absolute paths** were found in the application runtime
  code (the `/Users/...` strings are only in `DEPENDENCY_TESTING.md`, which also
  references `src/trend_analysis/...` paths that do not exist in this repo — stale doc
  copied from another project; out of scope but noted).

- **[MINOR] `setup_config_sheet.ps1` is a maintainer-only COM script**, correctly
  documented as requiring Excel + "Trust access to the VBA project object model"
  (setup_config_sheet.ps1:11-14, 60-68). Not on the operator path; fine as-is.

---

## Fresh-Windows-PC Path (step by step, with gaps)

What a non-technical operator would actually experience, assuming they receive the
`release.py`-produced bundle folder:

1. **Copy bundle folder to local disk.** `README_HOW_TO_RUN.md` (release.py:278-307)
   says copy the folder, edit `config/*.yml` if input paths changed, open
   `counter_risk_runner.xlsm`, enable macros, pick date/mode, click Run.
   - *Gap:* "edit YAML if input paths changed" assumes operator comfort editing YAML.

2. **Launch.** Either open the XLSM (macro path) or double-click `run_counter_risk.cmd`
   (fallback) or run `counter-risk gui`.
   - **Gap [MAJOR]:** First launch of the unsigned, UPX-packed `counter-risk.exe`
     triggers SmartScreen / AV. No operator instructions to bypass.

3. **Pipeline runs the calc + workbooks.** This is where the frozen build diverges from
   source:
   - **Gap [BLOCKER]:** Reconciliation crashes (`name_registry.yml` not found via
     `parents[3]`), aborting the run before outputs complete.
   - **Gap [MAJOR]:** Even if reconciliation were fixed, `limit_breaches.csv` is silently
     not produced (limits.yml not found via `parents[3]`).

4. **PowerPoint package.** Expected: deck with refreshed chart links + replaced
   screenshots.
   - **Gap [MAJOR]:** Frozen build has no `pywin32`, so it emits an un-refreshed deck
     plus `NEEDS_LINK_REFRESH.txt`. To get the real deliverable the operator must open
     the deck in PowerPoint and manually Update Links, OR run on a machine with Office +
     a Python env carrying `pywin32` (not no-install).

5. **Locate outputs.** With the worker `.cmd`, `--output-dir` is honored. With the GUI or
   a bare `counter-risk run`, default `runs/` resolves to the bundle's *parent* directory
   (run.py:818, 836-839), which is surprising.
   - *Gap [MINOR]:* default output location is non-obvious in the frozen build.

6. **Documentation.** There is **no operator-facing Windows setup/run document** in
   `docs/`. `docs/SETUP_CHECKLIST.md` is entirely CI/keepalive plumbing (not operator
   setup); `docs/gui_runner.md` targets someone who can run `pyinstaller release.spec`
   themselves; `README.md` mentions Windows only in passing (README:7, 218). The only
   operator doc is the auto-generated `README_HOW_TO_RUN.md` inside the bundle, which
   does not mention SmartScreen, the Office/pywin32 requirement for link refresh, or what
   to do when `NEEDS_LINK_REFRESH.txt` appears.

---

## Readiness Verdict

**Not Windows-ready for a true no-install operator path.** There is a coherent
*design* (frozen exe + bundled config/templates + XLSM runner + remote-request `.cmd`
worker), and most of the plumbing exists, but three issues block or hollow out the
deliverable:

1. **[BLOCKER]** Frozen-build path resolution: `reconciliation.py:23` (hard crash) and
   `run.py:2265` (silent loss of limit breaches) bypass `resolve_runtime_path` and assume
   the source-tree `parents[3]` layout. **Minimal fix:** route both through
   `resolve_runtime_path("config/name_registry.yml")` /
   `resolve_runtime_path("config/limits.yml")` (and likewise the bare `Path("config/...")`
   defaults in `name_registry.py:159`, `limits_config.py:98`, `normalize.py:25`), then add
   a frozen-mode test. Verify by building the exe and running an end-to-end fixture.

2. **[MAJOR]** The PowerPoint deliverable requires Office + `pywin32`, which the
   no-install bundle lacks. **Minimal fix:** decide and document the supported model —
   either (a) document that the final PPT link-refresh/screenshot step runs on an
   Office+Python machine (drop the "no-install" claim for that step), or (b) add
   `pywin32` as a Windows dependency and confirm PyInstaller bundles `win32com` so the
   exe can drive Office COM on an operator machine that has Office installed.

3. **[MAJOR]** Unsigned + UPX-packed exe → SmartScreen/AV friction with no operator
   guidance. **Minimal fix:** disable UPX (`upx=False`) for the operator build, add an
   Authenticode signing step in `release.py`, and add SmartScreen "Run anyway" guidance
   to `README_HOW_TO_RUN.md`.

Additional polish to reach a clean operator experience: write a dedicated
operator-facing Windows run doc (the current `docs/SETUP_CHECKLIST.md` is CI-only),
make the default `runs/` output location sensible in frozen mode, and validate the
frozen tkinter GUI actually launches on Windows.

Until item (1) is fixed, the frozen `.exe` cannot complete a run, so the practical
verdict is: today the only working operator path on Windows is one that runs from a
real Python environment (where `parents[3]` resolves correctly and `pywin32` can be
installed) — i.e., a dev/maintainer setup, not the intended no-install flow.
