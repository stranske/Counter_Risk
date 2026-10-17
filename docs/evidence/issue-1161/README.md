# Issue #1161 verification

Scope: accepted U04, All Programs once for unscoped caps. Source base:
`4c4a11d36b7a368524b26eee30d120efe3cb591b`. No other PR's payload was copied
or stacked. Canonicalization and policy amounts were unchanged.

## Causal proof

The archived results below describe the initial 33-case run. Follow-up checks
expand the absolute/share matrix to 34 cases: positive and negative authoritative
notionals, subset-first input order, and matching/unrelated subset entities across
all five dimensions. `followup-scope.txt` captures 34 GREEN, 29 RED with five
subset-free controls passing, and 34 GREEN after byte-identical source restoration.
The reproduction helper now derives the expected RED case count from its GREEN
run and always excludes slow tests. Running it with its output directory under
`/tmp/counter-risk-scope-followup/` verified four absolute cases RED/GREEN and all
45 named scope cases GREEN. Broader verification passed 284 tests:

```sh
pytest tests/compute/test_limits.py tests/test_limits_config.py tests/test_limit_monitoring_docs.py tests/pipeline/test_run_pipeline.py -m "not slow" -q
```

Verified acceptance:

- [x] The 200m + 150m overlap does not breach the 250m cap; authoritative 300m produces a 50m breach.
- [x] Matching and unrelated futures subsets cannot change All Programs percentage numerators or denominators.
- [x] CSV, manifest, data quality, RED status and exits agree; missing authority fails explicitly.
- [x] Restoring the original builder fails the scope gates; restoring fixed source bytes passes them.

Run `/opt/anaconda3/bin/python3 docs/evidence/issue-1161/reproduce_scope_gate.py`
from the repository root. It performs these steps serially:

1. Fixed scope: the two absolute-cap cases pass.
2. Restore only the original limit-row builder from the base commit: both cases
   fail assertions. The 200m + 150m case falsely reports 350m; the 300m case
   reports 450m instead of 300m. No guards or test assertions are weakened.
3. Restore the fixed source bytes and unchanged test bytes: both cases pass.
4. Run the 33 named scope acceptance cases: all pass, none skipped.

`proof.json`, the individual `*.binding.json` files, console logs and valid JUnit
bind raw argv, source/test SHA-256, outcomes and restoration. `original-builder.txt`
is the exact disconnected implementation. The script's `finally` restores source
bytes even if a gate fails. These are local causal results, not hosted CI acceptance.

## Acceptance and compatibility

- `acceptance.*`: 33 cases covering absolute and percentage universes, all five
  entity types, missing authoritative scope, subset-only missing entities, pipeline
  CSV/manifest/data-quality output and both pipeline and CLI exit paths.
- `compute-config.*`: 99 existing/new computation and configuration cases pass.
- `pipeline-compatibility.*`: existing mixed-granularity, fail/warning propagation
  and default/strict missing-entity pipeline cases.
- `black.*`, `ruff.*`, `mypy.*`: repository source/tests checks pass; Mypy checks
  106 source files. Black is the formatting authority.

`pipeline-artifacts/scenario-{0,1,2,3}` retains real acceptance-run CSV (when
breached), manifest and data-quality text. Scenarios 0/1 use the pipeline entry;
2/3 use the CLI. Even scenarios use 200m, odd scenarios 300m. The no-breach runs
are WARN from intentionally skipped report outputs, with no limit finding; breach
runs are FAIL/RED with one 50m fail breach. Tests retain all corresponding assertions.
Config loading, input validation/hashing, reconciliation, limits, concentration,
manifest and quality generation run normally against tiny real workbook inputs;
parsed tables are synthetic real pandas frames, and historical/report outputs
are doubled. Native Office rendering and production-data acceptance are unclaimed.

## Capability and operational boundary

Advisor `advice:b1099c7d60f9` ran before validation with opener/opener-lane and
repository binding. Shared-registry lock access was sandbox-denied; the same CLI
used an unchanged registry snapshot under the authorized measurement directory.
Every offered capability is explicitly declined in `capability-decisions.json`;
manual serialized proof and named runtime gates provide the requested evidence.
No gated capability was enabled or dispatched, and there was no second writer.

Earlier exploratory failures remain under
`~/.codex/orchestrator/measurement/issue-1161/`. They exposed unsuitable historical
fixtures for the no-failure control, relative paths resolved by the CLI against
its config directory, and an invalid empty limits list in the first missing-scope
fixture. Tiny real absolute-path inputs and a valid policy corrected those test
fixtures without changing production guards or weakening assertions. The first
proof-wrapper attempt also needed verbose pytest output to retain the numeric
350m false breach; the final serialized proof includes that output.

CI, provider review, exact-head merge gates, merge and source acceptance remain
pending after publication. The opener does not wait for them. Shared handoff and
claim-release outcomes are retained separately in the measurement receipt for
the parent; a reported helper success is not proof that a shared write persisted.
