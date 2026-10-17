# Limit Monitoring

The monthly pipeline evaluates configured exposure limits during each run and
writes breach artifacts beside the other run outputs. Limits are maintained in
`config/limits.yml`.

## Exposure universe

Current limits have no variant selector. Every enabled unscoped cap uses **All
Programs once**, selected before building limit exposure rows. Ex Trend and Trend
are overlapping reporting subsets and contribute neither exposure nor missing-entity
coverage to these caps. Absolute values remain gross magnitudes, including for
negative notionals. Percentage numerators and denominators both use All Programs;
counterparty caps use its totals and futures dimensions use its futures rows with
the existing granularity and canonical alias resolution.

If `all_programs` is absent, limit-row construction raises an explicit missing
**authoritative All Programs** error; the full pipeline also rejects missing parsed
variants during input validation. No subset fallback is allowed. An authoritative
scope with empty rows remains empty: enabled targets are reported missing under
the existing warning/strict policy. Missing limits configuration retains its
existing logged skip behavior.

## Configuration

Each `limits` entry has these fields:

| Field | Required | Meaning |
| --- | --- | --- |
| `entity_type` | yes | Dimension to evaluate: `counterparty`, `fcm`, `clearing_house`, `segment`, or `custom_group`. |
| `entity_name` | yes | Canonical entity key. Whitespace is collapsed to underscores and compared case-insensitively. |
| `limit_value` | yes | Positive threshold value. |
| `limit_kind` | yes | `absolute_notional` for gross notional caps or `percent_of_total` for share-of-total caps. |
| `severity` | no | `warning` or `fail`; defaults to `warning`. |
| `enabled` | no | Set `false` to document a staged policy without evaluating it; defaults to `true`. |
| `notes` | no | Operator-facing policy context included in breach records. |

Duplicate keys are rejected during config load. A key is the tuple
`entity_type`, normalized `entity_name`, and `limit_kind`.

## Safe Maintainer Update Process

Use this checklist when adding or revising a limit in `config/limits.yml`:

1. Find the canonical entity key used by pipeline outputs and set `entity_name`
   to that key (for example `citibank`, `cme`, or another normalized name).
2. Choose the smallest valid scope for `entity_type`:
   `counterparty`, `fcm`, `clearing_house`, `segment`, or `custom_group`.
3. Set `limit_kind` to match policy intent:
   `absolute_notional` for dollar caps, `percent_of_total` for concentration caps.
4. Set `severity` explicitly (`warning` or `fail`) and include `notes` explaining
   policy ownership or approval context.
5. If the limit is staged and not active, set `enabled: false` instead of removing
   the entry so history remains auditable.
6. Run validation tests before merging:
   `pytest tests/test_limits_config.py tests/compute/test_limits.py -m "not slow"`
7. Run one pipeline fixture test to confirm breach artifacts still render correctly:
   `pytest tests/pipeline/test_run_pipeline.py::test_run_pipeline_writes_limit_breaches_csv_when_breaches_exist -m "not slow"`
8. Run strict missing-entity coverage so bad canonical names fail fast in CI:
   `pytest tests/pipeline/test_run_pipeline.py::test_run_pipeline_strict_missing_limit_entities_fails -m "not slow"`

Practical edit pattern for maintainers:

1. Copy an existing entry in `config/limits.yml`.
2. Update `entity_type`, `entity_name`, `limit_kind`, and `limit_value`.
3. Set `severity` and `enabled` intentionally (avoid relying on defaults in policy PRs).
4. Add or update `notes` with approval context.
5. Run the three commands above before opening a PR.

Common validation failures and fixes:

- `duplicate limit keys are not allowed`: remove or merge entries that share
  the same `entity_type`, normalized `entity_name`, and `limit_kind`.
- `severity` validation errors: use only `warning` or `fail`.
- missing-entity warnings: correct `entity_name` to match exposure canonical
  keys, or set `strict_missing_entities: true` when the policy requires fail-fast behavior.

If a run warns that configured entities are missing, either correct `entity_name`
or intentionally set `strict_missing_entities: true` to fail fast in CI.

## Outputs

When one or more enabled limits breach, the run folder includes
`limit_breaches.csv` with deterministic rows:

- `entity_type`
- `entity_name`
- `limit_kind`
- `severity`
- `actual_value`
- `limit_value`
- `breach_amount`
- `notes`

The manifest includes `limit_breach_summary`, the warning list includes a
human-readable limit summary, and the run-folder `README.txt` shows a warning
banner with the highest observed severity.

## Missing Entities

If a configured enabled entity is not present in the All Programs exposure rows, the default
behavior is to add a manifest warning and continue. Set
`strict_missing_entities: true` to fail the run instead. Disabled limits are not
checked for missing entities.

## Scope verification (U04 / issue #1161)

Named gates in `tests/compute/test_limits.py` cover All Programs Citibank 200m
plus Ex Trend 150m against a 250m fail cap (no breach), and All Programs 300m
(50m breach). Percentage gates vary overlapping subsets across all five dimensions
and preserve the authoritative gross denominator and actual share. Subset-only
entities stay missing, including when the authoritative tables are empty.
The gates also place reporting subsets before All Programs in the input mapping,
vary matching and unrelated subset entities to challenge both sides of each share,
and verify negative authoritative notionals against the same absolute cap.

`test_all_programs_limit_scope_propagates_to_pipeline_and_exit` in
`tests/pipeline/test_run_pipeline.py` exercises existing pipeline/CLI control flow
with real pandas frames. A true 50m breach appears once in CSV and manifest, yields
a fail data-quality finding and RED summary, and raises in the pipeline / returns
CLI exit code 1. The 200m case has no breach artifact or limit failure and returns
CLI code 0. Parser frames and Office/report output boundaries are test doubles;
this does not claim native Office rendering or a fresh production-data run.
