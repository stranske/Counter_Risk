# U05 report-date verification

Accepted scope SHA-256: `eae261b8d126160a03fe8889b5149613cd48fe348291c5d1e067f49570c4b15c`.

The regression in `tests/test_dates.py::test_compare_source_dates_detects_later_variant_without_changing_precedence`
exercises a matching first source and a conflicting later source while retaining
configured-date authority. `scope-disconnect.patch` temporarily disconnects the
actual conflict signal in `src/counter_risk/dates.py`. The test fails by assertion
(`assert False is True`), not collection/import/runtime error. The source and test
are restored byte-identically before GREEN. `scope-proof.json` binds the scope,
source, test, mutation and restoration; the two JUnit files prove one failure with
zero errors, followed by one pass.

Each `*.binding.json` captures the actual interpreter/argv, working directory,
source/test SHA-256 values, exit code, raw console SHA-256, and JUnit SHA-256 where
applicable. `acceptance-final.*` covers the U05 cases, real parser/output pipeline,
bounded readers and existing MOSERS writer date behavior. `compatibility.*`
covers config, CLI, manifest/schema/quality surfaces and original date precedence.
`black.*`, `ruff.*` and `mypy.*` record the repository's required local static gates.
The real pipeline test emits only existing optional pandas accelerator warnings;
no runtime packages or host settings were changed.

Scope regressions use real bounded XLSX reads and the real config, date,
manifest/summary and CLI paths. Isolated stage spies prove strict/final containment
before history/publication and verify source files remain byte-identical. A separate
regression runs the actual parsers, calculations and output stages without those
spies. Override tests check its durable reason/run identity, retained YELLOW finding,
final-stage admission, and non-persistence on the next invocation.

The capability advisor's shared-registry lock was sandbox-denied. A read-only
snapshot consultation (`advice:a841eaa07fa9`, surface `opener-lane`) reported no
dispatch-ready capability. The deliberate-break helper was explicitly declined in
favor of this serialized causal proof; runtime AC and codemod dispatch were also
declined with reasons. Exact receipts, snapshot, decisions, full native ownership
readback and parent handoff artifacts are under
`~/.codex/orchestrator/measurement/issue-1162/`. These local results do not establish
hosted CI, provider review, merge, or source-issue acceptance.

Final results: 55 acceptance cases and 184 compatibility cases passed, with no
errors or skips. Black checked 292 files, Ruff passed, and mypy passed all 106
source files. `verification.json` records the checked JUnit/log/source bindings.
