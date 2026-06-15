# Pipeline Subsystem Audit

Summary: Orchestration in `run.py` is disciplined and consistent (every stage wrapped in try/except, stage-event recording, RuntimeError re-raise with operator messages). Manifest construction, schema validation, and reconciliation are high quality. The two material issues are (1) a green/yellow/red gap where a *fail*-severity limit breach never escalates the data-quality `overall_status` to RED, and (2) a dead, stale, buggy duplicate of `run_fixture_replay` in the shadowed top-level `pipeline.py` module. A fragile test-injection monkeypatch leaks into production reconciliation code.

## Summary

- Stage ordering and error propagation in `run_pipeline` (`run.py:358-676`) are consistent: each stage is wrapped, logs `pipeline_failed stage=...`, records a workflow-trace event on success/error, and re-raises a stage-scoped `RuntimeError ... from exc`. This is a strength.
- Manifest provenance integrity is solid: `_build_provenance` (`manifest.py:146-183`) is side-effect-free, `git_sha` is best-effort/nullable, and `ManifestBuilder.write` validates the schema *before* touching disk (`manifest.py:185-205`).
- Data-quality severity mapping is centralized and table-driven (`data_quality.py:11-60`), but the limit-breach path under-classifies fail-severity breaches.
- Reconciliation (`reconciliation.py`, `run.py:3640-3773`) has consistent failure handling and strict/warn policy support.

## Code Quality Findings

### [BLOCKER] Fail-severity limit breaches never turn the data-quality summary RED
- `data_quality.py:20` maps `LIMIT_BREACHES` to severity `"warn"` unconditionally, and `_collect_validation_findings` (`data_quality.py:225-234`) emits exactly one `warn`-level `LIMIT_BREACHES` finding regardless of breach severity.
- The pipeline computes a real fail/warning split: `_compute_and_write_limit_breaches` (`run.py:2295-2299`) counts `fail_breach_count` and sets `max_severity = "fail"`, and `_build_limit_breach_summary` (`run.py:2336-2344`) passes both `fail_breach_count` and `max_severity` into the summary that `ManifestBuilder.build` forwards to `build_data_quality` (`manifest.py:117-123`).
- `build_data_quality` ignores `fail_breach_count`/`max_severity` entirely. Consequently a hard (fail) limit breach yields `overall_status = "warn"` → YELLOW with guidance "Review warnings before sending." (`manifest.py:27-32`), instead of RED / "Do not send until failing checks are resolved."
- For a counterparty-risk distribution tool, a configured hard-limit breach not escalating the operator-facing summary to RED is a correctness/safety gap. Recommendation: emit a `fail`-severity `LIMIT_BREACHES` (or a distinct `LIMIT_FAIL_BREACHES`) finding when `limit_breach_summary["fail_breach_count"] > 0` / `max_severity == "fail"`.

### [MAJOR] Dead, stale, buggy duplicate module `src/counter_risk/pipeline.py`
- The package `src/counter_risk/pipeline/` shadows the sibling module `src/counter_risk/pipeline.py`; `import counter_risk.pipeline` always resolves to the package (`__init__.py`), confirmed at runtime. Nothing imports the top-level module by path; all callers use `counter_risk.pipeline.fixture_replay` (`cli/__init__.py:14`, `demo_artifact.py:13`).
- The dead module contains a copy of `run_fixture_replay` that is identical to the live `pipeline/fixture_replay.py` except it is missing the `if source_path is None: continue` guard (live version `fixture_replay.py:63-64`). The dead copy (`pipeline.py:62-65`) would raise `FileNotFoundError` on a `None` optional source. It is unreachable but actively misleading.
- Recommendation: delete `src/counter_risk/pipeline.py`.

### [MAJOR] Production reconciliation wrapper mutates module globals for test injection
- `reconcile_series_coverage` in `run.py:120-144` exists only to overwrite `reconciliation.normalize_counterparty_with_source` (a module global) with `run.normalize_counterparty_with_source` for the duration of one call, then restore it. Both names import the identical object from `counter_risk.normalize`, so the wrapper is a no-op in production and serves purely as a seam for the test that patches `counter_risk.pipeline.run.normalize_counterparty_with_source` (`tests/test_normalization_registry_first.py:236`).
- Mutating another module's `__globals__` at call time is fragile and not thread-safe (concurrent runs would race on the shared global). Recommendation: have reconciliation accept the resolver as a parameter (dependency injection), or have the test patch `counter_risk.pipeline.reconciliation.normalize_counterparty_with_source` directly and drop the wrapper.

### [MINOR] Stage-event name mislabels the parse/reconcile stage
- The combined prepare-config / parse / repo-cash / validate / reconcile block records its workflow-trace event as `"data-quality-summary"` (`run.py:465-471`), but the data-quality summary is not built here — it is produced later during manifest write (`manifest.py:_build_data_quality_summary`). The label misattributes latency/error to the wrong stage in observability traces.

### [MINOR] Non-standard JSON-Schema enum with `None` member
- `limit_breach_summary.max_severity` schema is `{"type": ["string","null"], "enum": ["warning","fail", None]}` (`manifest_schema.py:378`). The custom `_check_node` validator handles this, but `None` inside an `enum` is non-standard JSON Schema and will trip any external validator. Minor since validation is in-house.

## Duplication / Simplification Opportunities

- **Whole-file duplication:** `src/counter_risk/pipeline.py` duplicates `pipeline/fixture_replay.py` (and re-imports `ManifestBuilder` etc. via the package elsewhere). Removing the dead module eliminates the duplication outright (see MAJOR above).
- **Repeated input-path resolution:** `_resolve_input_paths` is invoked three times in one run — `run.py:399`, `run.py:448` (on `runtime_config`), and `run.py:640`. The first (pre-runtime-config) result is only used for validation; resolving once on `runtime_config` and reusing for parse + hashing would remove two redundant filesystem-resolution passes. Low risk, behavior-preserving.
- **Count derivation duplicated across modules:** `_build_counts` (`data_quality.py:335-354`) and `ManifestBuilder._derive_counts_from_findings` (`manifest.py:380-398`) implement the same by-severity / by-category tally over findings. The manifest copy is a defensive re-derivation for the summary text; consider sharing one helper to keep the two tally shapes from drifting.
- **`_safe_int` defined twice:** identical helper in `data_quality.py:328-332` and `ManifestBuilder._safe_int` (`manifest.py:400-404`). Candidate for a shared util.
- **Reconciliation helper indirection:** `_normalized_counterparties_from_records` / `_normalized_counterparties_from_parsed_data` / `_raw_counterparties_by_normalized_from_records` (`reconciliation.py:364-398`) are only reached through their own wrappers and tests; they are not used by `reconcile_series_coverage` itself (which uses `_counterparty_resolution_maps_from_records` and `_raw_counterparties_by_normalized_from_parsed_data`). They are re-exported through `run.py`'s `__all__` purely for tests. Not dead, but the layering is heavier than the production path needs.

## Notable Strengths

- **Consistent failure handling:** every orchestration stage in `run_pipeline` follows the same wrap/log/record-event/re-raise pattern with stage-scoped messages and `from exc` chaining (`run.py:379-672`); operator-facing messages are built for the high-value failure modes (missing inputs, parse, unmapped counterparties, reconciliation).
- **Validate-before-write manifest:** `ManifestBuilder.write` builds summary text, registers the summary artifact, and runs schema validation before any disk write, so a validation failure leaves no partial run directory (`manifest.py:185-205`).
- **Artifact-path hygiene:** `_to_relative_artifact_path` rejects `..` segments, absolute paths outside `run_dir`, and run-dir-self references (`manifest.py:523-545`), and `_validate_artifact_paths_exist` ensures declared outputs exist at write time (`manifest.py:547-556`).
- **Self-documenting schema layer:** `manifest_schema.py` ships a focused hand-rolled JSON-Schema subset validator with clear docstrings on the supported keywords and rationale for nullable `git_sha` and open-ended `details`.
- **Table-driven data-quality classification:** `_SEVERITY_BY_CODE` / `_CATEGORY_BY_CODE` (`data_quality.py:11-60`) plus message-token fallbacks keep severity/category mapping centralized and easy to extend.
