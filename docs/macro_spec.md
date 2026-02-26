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

