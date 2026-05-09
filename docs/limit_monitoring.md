# Limit Monitoring

The monthly pipeline evaluates configured exposure limits during each run and
writes breach artifacts beside the other run outputs. Limits are maintained in
`config/limits.yml`.

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

If a configured enabled entity is not present in the exposure rows, the default
behavior is to add a manifest warning and continue. Set
`strict_missing_entities: true` to fail the run instead. Disabled limits are not
checked for missing entities.
