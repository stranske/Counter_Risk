# Macro Specification

This document captures the current VBA macro behavior that must be preserved as the
pipeline replaces spreadsheet automation.

## Scope

- VBA module: `assets/vba/RunnerLaunch.bas`
- Workbook surface: `Runner.xlsm` and `assets/templates/counter_risk_template.xlsm`
- User-facing sheet: `Runner`

## Macro Intent (Plain Language)

### `RunAll_Click`

Runs the counter-risk pipeline in **All Programs** mode for the month selected on the
`Runner` sheet. It updates status/result cells so an operator can see whether execution
completed successfully.

### `RunExTrend_Click`

Runs the counter-risk pipeline in **Ex Trend** mode for the month selected on the
`Runner` sheet. It follows the same launch flow as `RunAll_Click`, but uses the Ex Trend
configuration.

### `RunTrend_Click`

Runs the counter-risk pipeline in **Trend** mode for the month selected on the `Runner`
sheet. It follows the same launch flow as the other run macros, but uses the Trend
configuration.

### `OpenOutputFolder_Click`

Opens the output directory for the currently selected reporting month so operators can
inspect generated artifacts. If the folder does not exist, it reports an error instead of
silently succeeding.

## Per-Macro Requirements

### `RunAll_Click`

Required inputs (sheet names, columns):
- Sheet `Runner`
- Cell `B3` with selected month text (`MM/YYYY`)
- Cell `B11` status output target
- Cell `B12` result output target
- Pipeline input workbook `tests/fixtures/NISA Monthly All Programs - Raw.xlsx`
- Parsed source fields from CPRS-CH totals rows: annualized volatility and notional

Output expectations (ranges affected, invariants):
- Writes status/result text to `Runner!B11:B12`
- Uses All Programs config for pipeline invocation
- Generated workbook includes `CPRS - CH`
- `CPRS - CH!B5` matches parsed lead counterparty from source
- `CPRS - CH!D10:D20` reflects annualized-volatility transformation
- `CPRS - CH!E10:E20` reflects notional-allocation transformation
- No blank numeric cells in `CPRS - CH!D10:E20`
- Headers in `CPRS - CH!C10:C20` match MOSERS template

### `RunExTrend_Click`

Required inputs (sheet names, columns):
- Sheet `Runner`
- Cell `B3` with selected month text (`MM/YYYY`)
- Cell `B11` status output target
- Cell `B12` result output target
- Pipeline input workbook `tests/fixtures/NISA Monthly Ex Trend - Raw.xlsx`
- Parsed source fields from CPRS-CH totals rows: annualized volatility and notional

Output expectations (ranges affected, invariants):
- Writes status/result text to `Runner!B11:B12`
- Uses Ex Trend config for pipeline invocation
- Generated workbook includes `CPRS - CH`
- `CPRS - CH!B5` matches parsed lead counterparty from source
- `CPRS - CH!D10:D20` reflects annualized-volatility transformation
- `CPRS - CH!E10:E20` reflects notional-allocation transformation
- No blank numeric cells in `CPRS - CH!D10:E20`
- Headers in `CPRS - CH!C10:C20` match MOSERS template

### `RunTrend_Click`

Required inputs (sheet names, columns):
- Sheet `Runner`
- Cell `B3` with selected month text (`MM/YYYY`)
- Cell `B11` status output target
- Cell `B12` result output target
- Pipeline input workbook `tests/fixtures/NISA Monthly Trend - Raw.xlsx`
- Parsed source fields from CPRS-CH totals rows: annualized volatility and notional

Output expectations (ranges affected, invariants):
- Writes status/result text to `Runner!B11:B12`
- Uses Trend config for pipeline invocation
- Generated workbook includes `CPRS - CH`
- `CPRS - CH!B5` matches parsed lead counterparty from source
- CPRS-CH annualized/allocation metric writes target the marker-resolved row block
  bounded by the `Goldman Sachs` and `Credit Agricole` rows before
  `Total by Counterparty/Clearing House`
- No blank numeric cells in the resolved CPRS-CH metric range
- Marker rows required for writes are present and ordered consistently

### `OpenOutputFolder_Click`

Required inputs (sheet names, columns):
- Sheet `Runner`
- Cell `B3` selected month text (`MM/YYYY`) for output folder resolution

Output expectations (ranges affected, invariants):
- Resolves output path using selected month and repository root
- Attempts to open folder path
- If path missing, reports an error status instead of silent success
- Does not mutate MOSERS workbook ranges

## Known-Acceptable Drift

- Floating-point comparisons for transformed numeric values use tolerance
  `rel_tol=1e-12` and `abs_tol=1e-12`.
- Allocation percentages in the resolved CPRS-CH metric allocation column are derived from
  `row.notional / sum(notional)` with no additional discretionary rounding in tests.
- Empty tail slots after available rows are accepted as blanks (`None`) in range-level
  checks, but invariant checks require non-blank values in the enforced core numeric
  ranges.
