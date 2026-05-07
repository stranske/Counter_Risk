# Macro Specification

This document captures the current VBA macro behavior that must be preserved as the
pipeline replaces spreadsheet automation. It is the machine-readable parity harness
referenced by the macro-equivalent test suite: each section is anchored by a stable
Spec ID (`MS-*`) so a failed parity test can point straight at the section it
protects.

## Scope

- VBA module sources: `assets/vba/*.bas` (canonical: `assets/vba/RunnerLaunch.bas`).
- Macro-enabled workbook fixtures (the source of truth for embedded module names):
  - `Runner.xlsm`
  - `assets/templates/counter_risk_template.xlsm`
- User-facing sheet: `Runner` (constant `RUNNER_SHEET_NAME`).
- Generated outputs: MOSERS workbooks per run mode (`All Programs`, `Ex Trend`,
  `Trend`); MOSERS structural invariants are documented per macro below and asserted
  in `tests/test_mosers_*_output_structure.py`.

## Runner Sheet Cell Layout

Spec ID: `MS-RUNNER-CELLS`

The Runner sheet uses a small set of named cells that every click handler reads or
writes. These are the source-of-truth constants in `RunnerLaunch.bas`; any drift
between the spec section and the `.bas` constants is a parity failure (see
`tests/test_macro_spec_parity.py`).

| Purpose                     | Cell | `.bas` constant            |
|-----------------------------|------|----------------------------|
| Selected as-of month input  | `B3` | (read by `ReadSelectedDate`) |
| Status output               | `B7` | `STATUS_CELL`              |
| Result output               | `B8` | `RESULT_CELL`              |
| Data quality status         | `B9` | `DQ_STATUS_CELL`           |

The selected-month cell `B3` accepts any value Excel parses as a date; macros
internally normalize to the last day of the parsed month before invoking the
pipeline.

## Macro Intent (Plain Language)

### `RunAll_Click`

Spec ID: `MS-RUN-ALL`

Runs the counter-risk pipeline in **All Programs** mode for the month selected on the
`Runner` sheet. It updates status/result cells so an operator can see whether
execution completed successfully.

### `RunExTrend_Click`

Spec ID: `MS-RUN-EX-TREND`

Runs the counter-risk pipeline in **Ex Trend** mode for the month selected on the
`Runner` sheet. It follows the same launch flow as `RunAll_Click`, but uses the Ex
Trend configuration.

### `RunTrend_Click`

Spec ID: `MS-RUN-TREND`

Runs the counter-risk pipeline in **Trend** mode for the month selected on the
`Runner` sheet. It follows the same launch flow as the other run macros, but uses
the Trend configuration.

### `OpenOutputFolder_Click`

Spec ID: `MS-OPEN-OUTPUT`

Opens the run output directory for the currently selected reporting month so
operators can inspect generated artifacts. If the folder does not exist, it reports
an error instead of silently succeeding.

### `OpenSummary_Click`

Spec ID: `MS-OPEN-SUMMARY`

Opens the data-quality summary file (`DATA_QUALITY_SUMMARY.txt`) inside the run
output directory for the selected reporting month. If the summary file is missing,
it reports an error in the result cell instead of silently succeeding.

### `OpenManifest_Click`

Spec ID: `MS-OPEN-MANIFEST`

Opens the run manifest (`manifest.json`) inside the run output directory for the
selected reporting month. If the manifest is missing, it reports an error in the
result cell instead of silently succeeding.

### `OpenPPTFolder_Click`

Spec ID: `MS-OPEN-PPT`

Opens the static PPT deliverable directory (`distribution_static/`) inside the run
output directory for the selected reporting month. If the directory is missing, it
reports an error in the result cell instead of silently succeeding.

## Per-Macro Requirements

### `RunAll_Click`

Spec ID: `MS-RUN-ALL`

Fixture sources:
- VBA module fixture: `assets/vba/RunnerLaunch.bas`
  (extracted from `Runner.xlsm` and `assets/templates/counter_risk_template.xlsm`)
- Pipeline input workbook fixture: `tests/fixtures/NISA Monthly All Programs - Raw.xlsx`
- Generated workbook fixture under test: produced by
  `counter_risk.mosers.workbook_generation.generate_mosers_workbook_all_programs`
  (asserted in `tests/test_mosers_all_programs_output_structure.py`)

Required inputs (sheet names, columns):
- Sheet `Runner`
- Cell `B3` with selected month text (`MM/YYYY`)
- Cell `B7` status output target (constant `STATUS_CELL`)
- Cell `B8` result output target (constant `RESULT_CELL`)
- Cell `B9` data quality status target (constant `DQ_STATUS_CELL`)
- Pipeline input workbook `tests/fixtures/NISA Monthly All Programs - Raw.xlsx`
- Parsed source fields from CPRS-CH totals rows: annualized volatility and notional

Output expectations (ranges affected, invariants):
- Writes status text to `Runner!B7` and result text to `Runner!B8`
- Writes data quality status (text + fill color) to `Runner!B9` when a
  `DATA_QUALITY_SUMMARY.txt` is produced; if no summary file is present, the VBA
  does not modify the existing `Runner!B9` value
- Uses All Programs config for pipeline invocation
- Generated workbook includes `CPRS - CH`
- `CPRS - CH!B5` matches parsed lead counterparty from source
- CPRS-CH annualized/allocation metric writes target the marker-resolved row block
  bounded by the `Goldman Sachs` and `Credit Agricole` rows before
  `Total by Counterparty/Clearing House`
- Default template anchor for the marker-resolved block remains `CPRS - CH!C10:C20`
  with values written to `CPRS - CH!D10:D20` and `CPRS - CH!E10:E20`
- No blank numeric cells in the resolved CPRS-CH metric range
- Marker rows required for writes are present and ordered consistently

### `RunExTrend_Click`

Spec ID: `MS-RUN-EX-TREND`

Fixture sources:
- VBA module fixture: `assets/vba/RunnerLaunch.bas`
- Pipeline input workbook fixture: `tests/fixtures/NISA Monthly Ex Trend - Raw.xlsx`
- Generated workbook fixture under test: produced by
  `counter_risk.mosers.workbook_generation.generate_mosers_workbook_ex_trend`
  (asserted in `tests/test_mosers_ex_trend_output_structure.py`)

Required inputs (sheet names, columns):
- Sheet `Runner`
- Cell `B3` with selected month text (`MM/YYYY`)
- Cell `B7` status output target (constant `STATUS_CELL`)
- Cell `B8` result output target (constant `RESULT_CELL`)
- Cell `B9` data quality status target (constant `DQ_STATUS_CELL`)
- Pipeline input workbook `tests/fixtures/NISA Monthly Ex Trend - Raw.xlsx`
- Parsed source fields from CPRS-CH totals rows: annualized volatility and notional

Output expectations (ranges affected, invariants):
- Writes status text to `Runner!B7` and result text to `Runner!B8`
- Writes data quality status (text + fill color) to `Runner!B9` when a
  `DATA_QUALITY_SUMMARY.txt` is produced
- Uses Ex Trend config for pipeline invocation
- Generated workbook includes `CPRS - CH`
- `CPRS - CH!B5` matches parsed lead counterparty from source
- CPRS-CH annualized/allocation metric writes target the marker-resolved row block
  bounded by the `Goldman Sachs` and `Credit Agricole` rows before
  `Total by Counterparty/Clearing House`
- Default template anchor for the marker-resolved block remains `CPRS - CH!C10:C20`
  with values written to `CPRS - CH!D10:D20` and `CPRS - CH!E10:E20`
- No blank numeric cells in the resolved CPRS-CH metric range
- Marker rows required for writes are present and ordered consistently

### `RunTrend_Click`

Spec ID: `MS-RUN-TREND`

Fixture sources:
- VBA module fixture: `assets/vba/RunnerLaunch.bas`
- Pipeline input workbook fixture: `tests/fixtures/NISA Monthly Trend - Raw.xlsx`
- Generated workbook fixture under test: produced by
  `counter_risk.mosers.workbook_generation.generate_mosers_workbook_trend`
  (asserted in `tests/test_mosers_trend_output_structure.py`)

Required inputs (sheet names, columns):
- Sheet `Runner`
- Cell `B3` with selected month text (`MM/YYYY`)
- Cell `B7` status output target (constant `STATUS_CELL`)
- Cell `B8` result output target (constant `RESULT_CELL`)
- Cell `B9` data quality status target (constant `DQ_STATUS_CELL`)
- Pipeline input workbook `tests/fixtures/NISA Monthly Trend - Raw.xlsx`
- Parsed source fields from CPRS-CH totals rows: annualized volatility and notional

Output expectations (ranges affected, invariants):
- Writes status text to `Runner!B7` and result text to `Runner!B8`
- Writes data quality status (text + fill color) to `Runner!B9` when a
  `DATA_QUALITY_SUMMARY.txt` is produced
- Uses Trend config for pipeline invocation
- Generated workbook includes `CPRS - CH`
- `CPRS - CH!B5` matches parsed lead counterparty from source
- CPRS-CH annualized/allocation metric writes target the marker-resolved row block
  bounded by the `Goldman Sachs` and `Credit Agricole` rows before
  `Total by Counterparty/Clearing House`
- Default template anchor for the marker-resolved block remains `CPRS - CH!C10:C20`
  with values written to `CPRS - CH!D10:D20` and `CPRS - CH!E10:E20`
- No blank numeric cells in the resolved CPRS-CH metric range
- Marker rows required for writes are present and ordered consistently

### `OpenOutputFolder_Click`

Spec ID: `MS-OPEN-OUTPUT`

Fixture sources:
- VBA module fixture: `assets/vba/RunnerLaunch.bas`
- Path resolution exercised against the run output directory under
  `<OutputRoot>/<yyyy-mm-dd_hhnnss>` per `ResolveOutputDir`

Required inputs (sheet names, columns):
- Sheet `Runner`
- Cell `B3` selected month text (`MM/YYYY`) for output folder resolution

Output expectations (ranges affected, invariants):
- Resolves output path using selected month and repository root
- Attempts to open the folder path
- If path missing, writes an error to `Runner!B8` instead of silent success
- Does not mutate MOSERS workbook ranges

### `OpenSummary_Click`

Spec ID: `MS-OPEN-SUMMARY`

Fixture sources:
- VBA module fixture: `assets/vba/RunnerLaunch.bas`
- Path resolution exercised against `<run-output-dir>/DATA_QUALITY_SUMMARY.txt`
  per `ResolveDataQualitySummaryPath`

Required inputs (sheet names, columns):
- Sheet `Runner`
- Cell `B3` selected month text (`MM/YYYY`) for summary path resolution

Output expectations (ranges affected, invariants):
- Resolves summary file path using selected month and repository root
- Attempts to open the file
- If file missing, writes an error to `Runner!B8` instead of silent success
- Does not mutate MOSERS workbook ranges

### `OpenManifest_Click`

Spec ID: `MS-OPEN-MANIFEST`

Fixture sources:
- VBA module fixture: `assets/vba/RunnerLaunch.bas`
- Path resolution exercised against `<run-output-dir>/manifest.json` per
  `ResolveManifestPath`

Required inputs (sheet names, columns):
- Sheet `Runner`
- Cell `B3` selected month text (`MM/YYYY`) for manifest path resolution

Output expectations (ranges affected, invariants):
- Resolves manifest file path using selected month and repository root
- Attempts to open the file
- If file missing, writes an error to `Runner!B8` instead of silent success
- Does not mutate MOSERS workbook ranges

### `OpenPPTFolder_Click`

Spec ID: `MS-OPEN-PPT`

Fixture sources:
- VBA module fixture: `assets/vba/RunnerLaunch.bas`
- Path resolution exercised against `<run-output-dir>/distribution_static` per
  `ResolvePPTOutputDir`

Required inputs (sheet names, columns):
- Sheet `Runner`
- Cell `B3` selected month text (`MM/YYYY`) for PPT folder resolution

Output expectations (ranges affected, invariants):
- Resolves PPT output folder path using selected month and repository root
- Attempts to open the folder
- If folder missing, writes an error to `Runner!B8` instead of silent success
- Does not mutate MOSERS workbook ranges

## Known-Acceptable Drift

Spec ID: `MS-DRIFT`

- Floating-point comparisons for transformed numeric values use tolerance
  `rel_tol=1e-12` and `abs_tol=1e-12`.
- Allocation percentages in the resolved CPRS-CH metric allocation column are derived from
  `row.notional / sum(notional)` with no additional discretionary rounding in tests.
- Empty tail slots after available rows are accepted as blanks (`None`) in range-level
  checks, but invariant checks require non-blank values in the enforced core numeric
  ranges.
- Cosmetic-only differences (cell fill color tints, font weight, column widths) are
  out of scope for parity tests; only structural and numeric invariants documented
  above are enforced.
