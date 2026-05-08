# Counterparty Name Registry

`config/name_registry.yml` is the maintained source of truth for counterparty
and clearing-house names used in parser, workbook, reconciliation, and report
matching paths.

Each entry must include:

- `canonical_key`: stable lowercase snake_case machine key.
- `display_name`: workbook/report label shown to users.
- `aliases`: raw names accepted from source data, including punctuation or legal-name variants.
- `series_included`: optional per-variant flags for historical series expectations.

When `series_included` is omitted, the series is expected in all variants. Set a
variant flag to `false` only when that counterparty is intentionally excluded
from that workbook variant, for example `trend: false`. Segment-specific
overrides live under `series_included.by_segment.<variant>.<segment>` and take
precedence over the variant default. Keep variant keys to `all_programs`,
`ex_trend`, or `trend`; keep segment keys lowercase and aligned with the parsed
series segment names used by reconciliation.

## Safe Update Process

Use this process whenever a source workbook, historical header, parser output,
or PowerPoint-facing reporting path introduces a new counterparty spelling:

1. Run the pipeline or mapping diff report first. Do not add aliases from memory.
2. For each `UNMAPPED` name, decide whether it is a new counterparty or a new
   spelling for an existing one.
3. Add new spellings to `aliases` under the existing `canonical_key` when the
   legal/entity identity is the same. Add a new entry only when the identity is
   distinct.
4. Keep `canonical_key` stable after it appears in reports. Rename only with a
   migration note and a focused regression test.
5. Use `display_name` for workbook, report, and PowerPoint-facing labels. Do
   not put presentation-only punctuation changes in `canonical_key`.
6. Add `series_included` only for intentional exclusions. Use `by_segment` when
   a variant includes one segment for a counterparty but excludes another.
7. Re-run validation before committing:

```bash
python -m pytest tests/test_name_registry.py tests/test_normalize.py tests/test_mapping_diff_report.py
```

8. Re-run the mapping diff report and confirm the edited name moved from
   `UNMAPPED` or repeated `FALLBACK_MAPPED` into `NAME_RESOLUTIONS` with the
   intended stable `key=...` value.

If two raw names normalize to the same alias token but refer to different
entities, stop and split the data source or requirements first. The registry
validator intentionally rejects cross-entry alias collisions so workbook/header,
parser, reconciliation, and PowerPoint-facing output paths keep using the same
canonicalization helper.

## Monthly Review

Run the mapping diff report after source files are parsed or when a run writes
`NEEDS_MAPPING_UPDATES.txt`:

```bash
python -m counter_risk.cli.mapping_diff_report \
  --registry config/name_registry.yml \
  --normalization-name "Raw Source Name" \
  --reconciliation-name "Workbook Header Name"
```

Review the report sections in this order:

- `UNMAPPED`: add a new registry entry or an alias on an existing entry.
- `FALLBACK_MAPPED`: move repeated fallback hits into explicit registry aliases.
- `SUGGESTIONS`: use only as a starting point; keep display names workbook-safe.
- `NAME_RESOLUTIONS`: verify the stable `key=` value matches the intended canonical key.

After editing the registry, run focused validation:

```bash
python -m pytest tests/test_name_registry.py tests/test_normalize.py tests/test_mapping_diff_report.py
```

Do not remove aliases just because a monthly source file stopped using them.
Keep historical aliases unless they collide with a different canonical key.
