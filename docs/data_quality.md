# Data Quality Reporting

Every successful pipeline run writes two shared quality surfaces:

- `manifest.json` includes a `data_quality` object.
- `DATA_QUALITY_SUMMARY.txt` gives operators a plain-English status, findings, counts, and next actions.

The status levels are:

- `info` / green: no action needed before sending outputs.
- `warn` / yellow: review warnings before sending outputs.
- `fail` / red: resolve failing checks before sending outputs.

## Adding Checks

New checks should add structured findings through `src/counter_risk/pipeline/data_quality.py` instead of writing a separate warning-only output. Prefer a stable uppercase `code`, one of the shared severity levels, a concise category, and an actionable message.

Use existing categories when possible. The categories currently emitted by `build_data_quality()` (see `_CATEGORY_BY_CODE` and the `pipeline` default) are:

- `input` — missing required or optional inputs.
- `mapping` — unmatched mapping entries.
- `reconciliation` — reconciliation gaps and gap detail.
- `limits` — limit breaches.
- `cash` — repo-cash sourcing, overrides, and limit findings.
- `ppt` — PPT generation status.
- `output_generation` — output generation skipped or failed.
- `data_validation` — invalid or missing notionals/descriptions.
- `date` — missing date header or fallback date resolution.
- `pipeline` — default category, including the `NO_FINDINGS` placeholder.

If a check already emits a pipeline warning, make sure `build_data_quality()` can classify the warning by code. If the check has richer context, pass that context into `ManifestBuilder.build()` so the manifest and summary can include counts and recommended actions without parsing free text.

## Operator Surfaces

The Excel/VBA Runner and the Tk Runner both read `DATA_QUALITY_SUMMARY.txt` after a successful run. They display the green/yellow/red quality label and provide an action to open the summary file. UI code should not inspect raw tracebacks for quality state; failures belong in command status, while run-quality findings belong in the shared summary and manifest object.

## Test Expectations

When adding a new data-quality check, include focused tests for:

- all-green behavior when the check has no findings,
- warning behavior when the check is advisory,
- failure behavior when outputs should not be sent,
- manifest schema shape and summary text for the new category or code,
- Runner status behavior if the operator-visible status changes.
