## Summary

When `config.as_of_date` is unset, compare legacy header-inferred as-of (effective) dates against every identified source report date. Surface `effective_date` and `effective_conflict_variants` separately from configured-date evidence (`configured_date` remains null).

## Scope

Retain legacy header inference and compare its effective date with every identified source date. Add `effective_date` and `effective_conflict_variants` separately from configured-date evidence, preserving `configured_date=null`. Reuse the existing diagnostics-first strict/final block and per-run override.

## Tasks

- [x] `src/counter_risk/dates.py` — optional `effective_date`; `effective_conflict_variants` in `has_conflict` and `status`
- [x] `src/counter_risk/pipeline/run.py` — supply resolved `as_of_date` and provenance in conflict diagnostics
- [x] `tests/pipeline/test_as_of_header_mismatch.py` — unset-config mismatch, diagnostic, strict/final, override, subsequent-no-override
- [x] `tests/test_dates.py` — effective-date evidence while preserving configured conflict semantics
- [x] `python3 -m pytest tests/pipeline/test_as_of_header_mismatch.py::test_inferred_as_of_mismatch_with_identified_sources_is_conflict -q`
- [x] `python3 -m pytest tests/pipeline/test_as_of_header_mismatch.py -q`
- [x] `python3 -m pytest tests/test_dates.py::test_compare_source_dates_detects_effective_mismatch_when_config_unset tests/test_dates.py::test_compare_source_dates_detects_later_variant_without_changing_precedence -q`

## Acceptance Criteria

- [x] Named test `tests/pipeline/test_as_of_header_mismatch.py::test_inferred_as_of_mismatch_with_identified_sources_is_conflict` (March 1 inference vs January 31 sources, `configured_date=null`) passes.
- [x] Deliberate break → revert: omit effective-date comparisons when `configured_date` is None; named test fails then passes after restore — `docs/evidence/issue-1253/effective-as-of-deliberate-break.md`.
- [x] Whole file passes: `python3 -m pytest tests/pipeline/test_as_of_header_mismatch.py -q`
- [x] Existing tests preserved: `tests/test_dates.py::test_compare_source_dates_detects_later_variant_without_changing_precedence` and configured-date pipeline assertions unchanged.

Deliberate-break evidence: `docs/evidence/issue-1253/effective-as-of-deliberate-break.md`

Verified on branch `cursor/issue-1253` at keepalive 2026-11-17 UTC (round 1256):

- `python3 -m pytest tests/pipeline/test_as_of_header_mismatch.py::test_inferred_as_of_mismatch_with_identified_sources_is_conflict -q` → 1 passed
- `python3 -m pytest tests/pipeline/test_as_of_header_mismatch.py -q` → 37 passed
- `python3 -m pytest tests/test_dates.py::test_compare_source_dates_detects_effective_mismatch_when_config_unset tests/test_dates.py::test_compare_source_dates_detects_later_variant_without_changing_precedence tests/test_dates.py::test_compare_source_dates_keeps_config_null_when_effective_matches_sources -q` → 3 passed
- `scripts/check_deliberate_break.py --head HEAD --pr-body-file docs/evidence/issue-1253/effective-as-of-deliberate-break.md` → verdict PASS

**Progress:** 8/8 tasks complete.

Apply this file when `gh` is unavailable in the runner (live PR checkboxes were stale after commits `fbae459`, `10a9486`, and `a880bfa`).

<!-- deliberate-break: test=tests/pipeline/test_as_of_header_mismatch.py::test_inferred_as_of_mismatch_with_identified_sources_is_conflict test-file=tests/pipeline/test_as_of_header_mismatch.py break-file=src/counter_risk/dates.py -->