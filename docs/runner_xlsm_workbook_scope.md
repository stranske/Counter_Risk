# Runner.xlsm Workbook Scope

## Objective

Create `Runner.xlsm` with the chosen **month selector** date control so non-technical operators can pick an `as_of_date` month-end value without CLI usage.

## In Scope

- Build `Runner.xlsm` at repository root as the runner workbook artifact.
- Include visible `Runner` sheet and hidden `ControlData` sheet.
- Place the month selector label in `A3` and input cell in `B3`.
- Populate `ControlData!A2:A193` with deterministic month-end values (`2020-01-31` to `2035-12-31`).
- Bind a list validation on `Runner!B3` to `ControlData!$A$2:$A$193`.
- Keep scope encoded in `counter_risk.runner_date_control.define_runner_xlsm_workbook_scope` so tests can assert boundaries.

## Out Of Scope

- Run-mode button click handling.
- Executable launch and process management.
- Post-run status/log capture and output-folder open behavior.

## Verification

- `tests/test_runner_workbook_scope.py` validates scope defaults and builder integration.
- `tests/test_runner_workbook.py` validates committed workbook structure and month-selector wiring.
