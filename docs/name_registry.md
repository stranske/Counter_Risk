# Name Registry Maintainer Process

The name registry at `config/name_registry.yml` is the canonical source of
counterparty and clearing-house aliases used by the Counter Risk pipeline.
Parsers and writers route through `counter_risk.normalize.resolve_counterparty`
and `resolve_clearing_house`, which consult the registry first and fall back to
a small set of hardcoded mappings only when the registry has no match.

This page explains how to update the registry safely.

## Schema

```yaml
schema_version: 1
entries:
  - canonical_key: bank_of_america         # snake_case identifier, globally unique
    display_name: Bank of America          # workbook/PPT label
    aliases:                               # at least one; deduplicated case/whitespace
      - Bank of America
      - Bank of America NA
    series_included:                       # optional; defaults to all-True when omitted
      all_programs: true
      ex_trend: true
      trend: true
```

The schema is enforced by `counter_risk.name_registry.NameRegistryConfig`
(pydantic). Aliases collide if any two normalized forms (apostrophe, dash, and
whitespace canonicalization plus casefold) clash across different
`canonical_key`s. The validator rejects collisions and duplicate
`canonical_key`s outright.

## Adding or editing an entry

1. Decide whether the new name belongs to an existing entry (add an alias) or
   needs its own `canonical_key` (separate counterparty).
2. Edit `config/name_registry.yml`. Keep `canonical_key` snake_case
   (`^[a-z0-9]+(?:_[a-z0-9]+)*$`); set `display_name` to the label that should
   appear in workbook headers and PPT outputs.
3. Add every observed spelling to `aliases`. Curly quotes, em-dashes, and
   doubled spaces are normalized at lookup time, so you do not need to repeat
   punctuation variants.
4. Validate before committing:

   ```bash
   python -c "from counter_risk.name_registry import load_name_registry; load_name_registry()"
   ```

   A `ValueError` with `Name registry validation failed:` is raised if the
   schema, alias collision, or duplicate-key rules are violated. Surface the
   exact offending field from the message and fix it.
5. Run the focused tests:

   ```bash
   python -m pytest tests/test_name_registry.py tests/test_normalization_registry_first.py
   ```

## Per-variant inclusion flags

Some counterparties belong to certain reporting variants only. Use
`series_included` to express that. The flag set is:

| Variant | Description |
| --- | --- |
| `all_programs` | Combined all-programs reporting |
| `ex_trend` | Ex-Trend (LLC) reporting |
| `trend` | Trend-only reporting |

Omit the block when the entry should appear in every variant. When present, all
three keys are required (pydantic `extra=forbid`). At runtime call
`NameRegistryConfig.is_series_included(canonical_key, variant)` to check
whether a name participates in a given variant; unknown canonical keys default
to `True` so the pipeline does not silently drop names the registry has not yet
caught up to.

## Finding unmapped names

Run the mapping diff report whenever you ingest a new month or onboard a new
data source. It compares observed raw names against the registry and groups
them as unmapped, fallback-mapped, or registry-mapped:

```bash
python -m counter_risk.cli.mapping_diff_report \
  --normalization-name "Bank of America NA" \
  --normalization-name "Citigroup" \
  --reconciliation-name "ICE Clear Europe"
```

Output sections:

- `UNMAPPED` — raw names with no registry or fallback hit. Add these to the
  registry as new `canonical_key`s or as aliases on an existing entry.
- `FALLBACK_MAPPED` — names matched only by the legacy fallback table in
  `counter_risk.normalize`. Promote them into the registry to keep
  `source="registry"` for new outputs.
- `SUGGESTIONS` — title-cased candidates for unmapped names; treat as a starting
  point only.
- `NAME_RESOLUTIONS` — full per-name trace for review.

## Review checklist

Before merging an edit:

- [ ] `canonical_key` is snake_case and unique across the file.
- [ ] At least one alias exists for every entry.
- [ ] No alias is shared across different `canonical_key`s after
      whitespace/apostrophe/dash canonicalization.
- [ ] `display_name` matches what should appear in operator-facing outputs.
- [ ] `series_included` is set only when at least one variant should be
      excluded.
- [ ] `python -m pytest tests/test_name_registry.py` passes.
- [ ] Mapping diff report on the latest source data shows zero `UNMAPPED`
      counterparties (or each one has a recorded reason for staying out).
