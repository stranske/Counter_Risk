# io-config Subsystem Audit

Summary: The configuration-loading and name-canonicalization substrate is in good shape overall — Pydantic models with `extra="forbid"` mean typo/unknown YAML keys are reliably caught at load time, and validation/error reporting is uniform and operator-friendly. The main weaknesses are (1) inconsistent strictness across the three structurally-identical YAML loaders (only `limits_config` rejects duplicate keys; `config` and `name_registry` silently take "last wins"), and (2) substantial structural duplication: three copies of the load+validate+error-format scaffold, two copies of the apostrophe/dash canonicalization regexes, and two dead/unused symbols.

## Summary

Files reviewed: `config.py`, `limits_config.py`, `name_registry.py`, `name_matching.py`, `normalize.py`, `dates.py`, `formatting.py`, `runtime_paths.py`, and `io/*.py` (`__init__.py`, `errors.py`, `discover.py`).

Strengths first: every config schema uses `model_config = ConfigDict(extra="forbid")`, so unknown/typo keys raise a `ValidationError` rather than being silently dropped — this directly answers the "are typo config keys caught?" question with a confident yes for top-level and nested models. Loaders consistently coerce `None`/non-mapping top-level YAML into clear errors, and the three `_format_*_validation_error` helpers produce readable `field: message` output. Cross-entry uniqueness (output-generator names, limit keys, registry canonical keys + alias collisions) is validated thoroughly.

The findings below are mostly about *consistency* and *condensation*, not correctness. There are no BLOCKERs.

## Code Quality Findings

### [MAJOR] Inconsistent duplicate-key handling across YAML loaders
- `limits_config.py:12-30` installs a `_NoDuplicateSafeLoader` that raises on duplicate mapping keys.
- `config.py:184` (`load_config`) uses plain `yaml.safe_load`, and `name_registry.py:164` (`load_name_registry`) also uses plain `yaml.safe_load`.
- Verified empirically: a `config` YAML with `export_pdf: false` followed by `export_pdf: true` loads without error and silently takes the last value (`cfg.export_pdf == True`). For an operator hand-editing `all_programs.yml`, an accidental duplicated key is silently swallowed.
- Recommendation: promote `_NoDuplicateSafeLoader` to a shared module (e.g. `name_matching`-adjacent or a small `yaml_utils`) and use it in all three loaders. This is the single most user-impactful inconsistency for local operators editing config by hand.

### [MINOR] Dead code: `_normalize_whitespace` in normalize.py
- `normalize.py:108-114` defines `_normalize_whitespace`, documented as deprecated in favor of `canonicalize_name`. `grep` across `src/` shows the only occurrence is its own definition — it has no callers.
- Recommendation: delete it.

### [MINOR] Dead code: `_OPTIONAL_INPUTS` in discover.py
- `discover.py:226-228` defines `_OPTIONAL_INPUTS: frozenset[str]`. It is never referenced anywhere in `io/` or the wider package (the `pipeline/data_quality.py` hits for "OPTIONAL_INPUTS" are an unrelated string constant `"MISSING_OPTIONAL_INPUTS"`).
- Recommendation: delete it, or wire it into `resolve_discovery_selections` if it was intended to gate the 0-match case.

### [MINOR] `cash_total_min` has no standalone validation; range check is one-sided
- `config.py:159-167` validates `cash_total_max >= cash_total_min`, but only fires when `cash_total_max` is provided. There is no lower/upper sanity check on `cash_total_min` alone (e.g. negative values) and no validator on `cash_total_min` itself. This is minor because the relationship check covers the common case, but a config with only `cash_total_min` set is entirely unvalidated.
- Recommendation: if negatives are nonsensical for a cash total, add `ge=0` or a small validator; otherwise document that single-sided bounds are intentional.

## Duplication / Simplification Opportunities

### [MAJOR] Three near-identical load + validate + error-format scaffolds
`config.py:170-199`, `limits_config.py:89-120`, and `name_registry.py:150-179` each implement:
1. a `_format_*_validation_error(error)` function that is byte-for-byte identical except the leading header string, and
2. a `load_*` function with the same structure: `Path(path)` → read text → catch `OSError`/`yaml.YAMLError` → reject non-`dict` top level → `Model.model_validate` → wrap `ValidationError` via the formatter.
- Recommendation: extract a single generic helper, e.g.
  `load_yaml_model(path, model_cls, *, kind: str, loader=SafeLoader) -> Model`,
  plus one `format_validation_error(error, header)`. This would remove ~60 lines of duplicated control flow and, as a bonus, naturally fixes the duplicate-key inconsistency above (one loader argument, applied everywhere). Behavior is preserved because the three bodies differ only in the model class and the human-readable label.

### [MAJOR] Duplicated apostrophe/dash canonicalization regexes and logic
- `name_matching.py:8-11` and `normalize.py:29-32` define the *identical* `_APOSTROPHE_RE` and `_DASH_RE` patterns.
- `normalize.canonicalize_name` (`normalize.py:88-90`) is exactly `name_matching.canonicalize_match_key` (`name_matching.py:17-19`) minus the trailing `.casefold()`.
- Recommendation: have `normalize.py` import the regexes from `name_matching`, or refactor so `canonicalize_match_key(x)` is defined as `canonicalize_name(x).casefold()` (or vice versa) in one place. This removes a real drift hazard: if one dash variant is added to one regex but not the other, matching and display normalization would diverge silently.

### [MINOR] `resolve_counterparty` and `resolve_clearing_house` share most of their body
- `normalize.py:155-188` and `normalize.py:214-252` differ only in (a) the fallback mapping dict and (b) the `source` label used on the no-match branch (`"unmapped"` vs `"fallback"`).
- Recommendation: a small private `_resolve(name, fallback_map, *, unmatched_source, registry_path)` would collapse the two into one body. Lower priority than the two MAJOR dedup items because the divergence (different terminal `source`) is behaviorally meaningful and well-commented.

### [MINOR] Repeated `data = raw if raw is not None else {}` + non-mapping guard
The same three-line guard appears in all three loaders (`config.py:190-194`, `limits_config.py:111-115`, `name_registry.py:170-174`). Folded naturally into the `load_yaml_model` helper proposed above.

## Notable Strengths

- `extra="forbid"` on every model (`ReconciliationConfig`, `InputDiscoveryConfig`, `OutputGeneratorConfig`, `WorkflowConfig`, `LimitEntry`, `LimitsConfig`, `SeriesIncludedFlags`, `NameRegistryEntry`, `NameRegistryConfig`) means typo'd or unknown config keys are caught at load, not silently ignored — the core concern of this audit is well-handled.
- `runtime_paths.resolve_runtime_path` (`runtime_paths.py`) is a clean, well-documented PyInstaller-frozen-vs-source resolver with deduped bundle roots and an actionable error message listing every searched location — good for Windows .exe operators.
- `normalize.py` cleanly separates the *matching key* (casefolded, punctuation-normalized) from the *display name* (whitespace-only), with docstrings explaining exactly when to use each — a common source of bugs handled deliberately.
- Name registry validation is rigorous: snake_case `canonical_key` pattern, alias dedupe after normalization, and global alias-collision detection across entries (`name_registry.py:126-147`).
- `dates.py` date resolution returns provenance (`source` + `details`) and is robust to both mapping- and iterable-shaped CPRS headers with multi-format date coercion.
- Registry alias lookup is `lru_cache`d on a resolved path string (`normalize.py:131`), and path resolution is cwd-independent with a repo-root fallback (`normalize.py:117-128`) — appropriate for the frozen-exe and GUI launch contexts.
