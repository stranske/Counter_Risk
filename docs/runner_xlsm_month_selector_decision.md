# Runner.xlsm Date Input Decision

## Decision

Use a **month selector** dropdown in `Runner.xlsm` rather than an Excel date picker control.

## Rationale

- The operator workflow is month-based (`as_of_date` reports are run at month-end).
- Native Excel date picker controls are not uniformly available/reliable across Office versions and macro security settings.
- A worksheet data-validation dropdown is deterministic, testable in CI, and does not require ActiveX controls.

## Initial Implementation Scope

- `Runner.xlsm` includes a visible `Runner` sheet.
- Cell `B3` is the month selector control.
- Month options are sourced from a hidden `ControlData` sheet (`A2:A193`, month-end dates).
- This slice implements date/month selection only; run buttons and execution VBA are handled in subsequent tasks.
