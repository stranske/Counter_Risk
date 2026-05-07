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
from that workbook variant, for example `trend: false`.

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
