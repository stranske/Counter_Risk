# Windows Operator Runbook

Step-by-step guide for producing a Counter Risk report package on a Windows PC
using the pre-built frozen executable.  No Python development environment is
required for the data/workbook steps; the PowerPoint link-refresh step requires
Microsoft Office and a Python environment (see Step 5).

---

## Prerequisites

- Windows 10 or Windows 11 (64-bit).
- The Counter Risk bundle folder supplied by the maintainer (contains `bin\`,
  `config\`, `templates\`, `counter_risk_runner.xlsm`,
  `run_counter_risk.cmd`).
- Monthly input files placed in the paths configured in `config\*.yml`
  (ask your maintainer if the paths need updating).

---

## Step 1 — Copy the Bundle to a Local Folder

Copy the entire bundle folder to a local drive (e.g. `C:\CounterRisk`).
Network shares work but local paths avoid permission issues with Windows
Defender.

---

## Step 2 — First-Run SmartScreen Bypass (unsigned executable)

The `bin\counter-risk.exe` is not code-signed.  Windows SmartScreen will
show "Windows protected your PC" on first launch.

**To proceed:**
1. Click **More info**.
2. Click **Run anyway**.

> **Note for IT/corporate environments:** If policy blocks unsigned executables
> entirely, the maintainer must sign `counter-risk.exe` with an Authenticode
> certificate.  See the signing note in `release.spec` for the `signtool`
> command.

---

## Step 3 — Edit Config if Input Paths Changed

Open `config\all_programs.yml` (and `ex_trend.yml` / `trend.yml` as needed)
in Notepad.  Update the file paths under `mosers_*`, `hist_*`, and
`monthly_pptx` to point at this month's input files.

---

## Step 4 — Run the Pipeline

**Option A — XLSM Runner (recommended for non-technical operators):**
1. Open `counter_risk_runner.xlsm` in Excel.
2. Enable macros when prompted.
3. Select the report date and variant from the dropdowns.
4. Click the **Run** button (or press Alt+F8 → `RunAll_Click` → Run).

**Option B — Command prompt:**
```
run_counter_risk.cmd
```
Double-click the file, or open a command prompt and run it from the bundle
folder.

**Option C — GUI:**
```
bin\counter-risk.exe gui
```

Outputs are written to `runs\<date>\` inside the bundle folder.

---

## Step 5 — PowerPoint Link Refresh (requires Office + pywin32)

The frozen `.exe` produces a PowerPoint deck but **cannot refresh chart links
or replace screenshots** — these steps require Microsoft Office's COM
automation (`pywin32`), which the no-install bundle does not include.

**If you see `NEEDS_LINK_REFRESH.txt` in the output folder:**

1. Open the deck in PowerPoint.
2. When prompted "This presentation contains links", click **Update Links**.
3. Save and close.

**To get fully automated screenshot replacement and link refresh:**

Install Python (≥3.12) and run:
```
pip install pywin32
pip install -e .   # from the Counter Risk source tree
python -m counter_risk.cli run --config config\all_programs.yml
```
`pywin32` is declared as a Windows-only dependency in `pyproject.toml` and
will be installed automatically on Windows.

---

## Step 6 — Locate Outputs

All outputs are written to:
```
<bundle folder>\runs\<YYYY-MM-DD>\
```

Key files:
| File | Description |
|------|-------------|
| `monthly_report.xlsx` | Historical workbook |
| `Monthly Counterparty Exposure Report.pptx` | PowerPoint deck |
| `limit_breaches.csv` | Limit breach log (empty if no breaches) |
| `manifest.json` | Run provenance / data-quality summary |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| SmartScreen blocks exe | Unsigned exe | Click More info → Run anyway |
| "Unable to read config file" | Path in `config\*.yml` not found | Update the file path |
| PowerPoint not refreshed | No pywin32 / Office | See Step 5 |
| "Configuration validation failed" | YAML syntax error in config | Re-check indentation; YAML is whitespace-sensitive |
| Blank limit_breaches.csv | No breaches detected | Expected when within limits |

---

## Maintainer Notes

- Re-build the exe after any source change: `python -m counter_risk.build.release`.
- Sign the exe with `signtool` (see `release.spec` for the exact command) to
  eliminate SmartScreen prompts in corporate environments.
- Regenerate lock files on Windows after adding dependencies:
  `uv pip compile --python-version 3.12 pyproject.toml --extra dev --universal --output-file requirements.lock`
