# Runner XLSM Manual Macro Verification

Use this checklist on a Windows machine with desktop Excel when validating macro/button behavior for a generated workbook.

## Preconditions

- Microsoft Excel with VBA macros enabled for trusted/signed workbooks.
- `dist/counter-risk.exe` built and present (or equivalent packaged executable).
- Generated workbook from the template builder, for example:

```bash
python -m counter_risk.build.xlsm \
  --template-path assets/templates/counter_risk_template.xlsm \
  --output-path dist/counter_risk_runner.xlsm \
  --as-of-date 2026-01-31 \
  --run-date 2026-02-26T12:00:00+00:00 \
  --version 1.2.3
```

## Manual Macro/Button Check

1. Open `dist/counter_risk_runner.xlsm` in Excel.
2. If prompted, click **Enable Content** so macros are active.
3. Confirm the `Runner` sheet is present and shows action controls for:
   - `Run All`
   - `Run Ex Trend`
   - `Run Trend`
   - `Open Output Folder`
4. Open **Developer > Macros** and verify these macro names exist:
   - `RunAll_Click`
   - `RunExTrend_Click`
   - `RunTrend_Click`
   - `OpenOutputFolder_Click`
5. Select a valid month in cell `B3` on the `Runner` sheet.
6. Trigger each run button once (`Run All`, `Run Ex Trend`, `Run Trend`) and verify:
   - Status cell `B7` transitions through launch states and ends at `Complete`.
   - Result cell `B8` reports `Success`.
   - A timestamped folder is created under `runs/`.
7. Trigger `Open Output Folder` and verify the run folder opens in Windows Explorer.

## Version Bump Regression Check

1. Rebuild the workbook with a new pipeline version value, for example `--version 1.2.4`.
2. Repeat the full **Manual Macro/Button Check** above on the newly generated workbook.
3. Confirm the same macro names are still present and all button actions still complete successfully.
4. Record the tested versions and outcome in the PR notes or release validation log.
