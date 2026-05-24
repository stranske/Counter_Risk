# LangSmith Fleet Artifact

Counter_Risk writes a dashboard-safe `langsmith-fleet.ndjson` file into each
monthly run folder. The file follows the Workflows-owned `langsmith-fleet/v1`
contract for `stranske/Counter_Risk#610` and lets the fleet dashboard inspect
risk/report observability without reading sensitive exposure or report payloads.

## Records

Each run emits one record for each risk-reporting operation:

- `data-quality`
- `risk-proxy`
- `limit-monitoring`
- `report-generation`

The shared fields include repo, surface, operation, run ID, status, owning issue,
recorded timestamp, and `error_category`. If runtime code supplies trace latency,
records also include `latency_ms`. The domain block includes:

- `as_of_date`
- `scenario`
- `data_quality_status`
- `limit_breach_count`
- `limit_scope`
- operation-specific counts or artifact references

Artifact references use `artifact:<relative-path>` values. Raw counterparty
positions, exposure records, notional data, report text, prompt text, and model
outputs are not written to this artifact. `validate_fleet_records()` enforces
the local Workflows fleet-contract subset before the NDJSON file is written:
required top-level fields, required domain fields, allowed statuses, safe
`artifact:` references, and a deny-list for sensitive payload fields.

## LangSmith Configuration

When `LANGSMITH_API_KEY` is present, Counter_Risk defaults LangSmith tracing to
the repo-specific project `counter-risk` and mirrors the key into
`LANGCHAIN_API_KEY` for LangChain clients. Without a key, the fleet records use
status `no_secret`; the pipeline still succeeds and no network call is required.

Operators can correlate records with LangSmith by setting `LANGSMITH_TRACE_ID`
or `LANGSMITH_TRACE_URL` in runtimes that already know the trace reference. The
pipeline records correlate these workflow artifacts by relative artifact
reference:

- `DATA_QUALITY_SUMMARY.txt` for data-quality warnings and fallbacks
- `concentration_metrics.csv` for concentration metric availability
- `limit_breaches.csv` and `manifest.json` for limit breach counts/severity
- generated workbook and presentation files for report-generation status

## Validation

For focused local validation, run:

```bash
python -m pytest tests/observability/test_langsmith_fleet.py tests/test_langchain_runtime.py -q
```

For pipeline insertion-point coverage, run:

```bash
python -m pytest tests/pipeline/test_run_pipeline.py -q
```
