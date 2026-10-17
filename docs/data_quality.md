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

## Source report-date consistency (U05)

`config.as_of_date` remains authoritative. The existing config-first resolution,
first-parsable-header fallback when config is unset, and `run_date` precedence and
clock fallback are unchanged. Comparison is independent of resolution: every
identified workbook date participates, including later variants after a matching
first workbook. With config unset, distinct source dates still produce a conflict;
the original fallback selection is retained.

Before any generated workbook is created, the pipeline collects evidence for
`all_programs`, `ex_trend`, and `trend`, recording variant, input path, observed
header text, and report date. Scans are limited to rows 1–15 and columns A–F on
the first worksheet and the explicitly named `CPRS - CH` worksheet (if present).
No other worksheets or body rows are searched. The legacy fallback still uses
only the original first-worksheet scan. Readers close on success and failure.

Independent evidence must start with a report-date label (`Report Date`,
`As Of [Date]`, including underscore/hyphen separators) immediately followed by a
single valid calendar date: `YYYY-MM-DD`, `M/D/YYYY`, or `M/D/YY` (month first).
Labels are case-insensitive; whitespace and an optional colon may separate the
label from the date. Two-digit years `00`–`68` mean 2000–2068, and `69`–`99` mean
1969–1999; four-digit years avoid that ambiguity. Comparisons use exact calendar
date equality, without month-end normalization or timezone conversion.

Unrelated dates such as creation, settlement, or prior-report tokens do not confirm
the report period. Repeated labeled lines identifying the same date are accepted.
Multiple distinct dates, multiple date-like tokens on one labeled line (even
repeated dates), or an invalid labeled date make the workbook ambiguous. A
malformed additional token must not be silently discarded: for example,
`Report Date: 2026-01-31 / 2026-02-300` and
`Report Date: 2026-01-31 / 2026-02-28T23:00:00` are ambiguous, rather than confirmed
January dates. Missing paths, unreadable workbooks, and absent labels are unverified.
These states cannot establish a confirmed match or mismatch. Other reliably
identified workbooks can still conflict even if one workbook is unverified.

Config-stamped generation is not independent confirmation: raw-NISA replacement
variants, headers explicitly marked generated from config, and the writer's
reserved legacy `CPRS CH Header Date` stamp are classified `generated`. New stamps
also carry an explicit provenance notice in C3. This conservative treatment of
legacy stamps prevents older generated files from validating their own config date.

`date_resolution.source_report_dates` in `manifest.json` records all source
classifications, configured date, conflict variants, inter-variant conflict, policy,
execution disposition, and any run-level override. A confirmed conflict emits
`SOURCE_REPORT_DATE_CONFLICT`, category `date`, severity `warn`, with the same
structured details under the shared quality finding. Its message and
`DATA_QUALITY_SUMMARY.txt` record the dates and source paths/variants. The shared
status is YELLOW unless another finding raises it to RED. Consistent identified
sources emit no mismatch finding; `unverified` never means a verified match.

The comparison policy defaults to `report_date_policy: warn`. Diagnostic runs
continue with advisory YELLOW findings. For a diagnostic-only run, disable
`enable_ppt_output`, `enable_distribution_output`, and `export_pdf`, and use
`output_generators: []` (or disable all historical generators). Setting
`report_date_policy: strict` blocks confirmed conflicts even in diagnostic runs.

Final publication/history execution always enforces strict handling: any enabled
historical generator, PPT output, distribution output, or PDF export blocks a
confirmed conflict before runtime workbook generation, history updates, or
publication. This applies even when the comparison policy is `warn`. The pipeline
first durably writes `manifest.json` and `DATA_QUALITY_SUMMARY.txt` with
`execution: blocked`, then raises `RuntimeError`; workflow CLI returns exit 1.
The date finding remains YELLOW because it describes the evidence; the nonzero
exit and blocked disposition prohibit publication. Failed/blocked run folders are
diagnostic artifacts, not completed reporting packages.

Correct conflicting source periods and rerun. A deliberate exception requires an
explicit **run-level** audit reason: `counter-risk run --config workflow.yml
--report-date-override "Risk owner approved period exception REF-42"`. API callers
pass `report_date_override` to `run_pipeline` or `run_pipeline_with_config`. Blank
reasons are rejected. The reason, run date, and unique run folder are persisted in
the manifest, and `SOURCE_REPORT_DATE_OVERRIDE` puts the reason in the shared
summary. An override permits this run's final stages, preserves the conflict
finding and configured date, and is never saved as a reusable config setting.
Operators must review the reason; this mechanism records their decision rather
than proving external authorization. Unverified evidence alone does not trigger
strict mismatch failure.
