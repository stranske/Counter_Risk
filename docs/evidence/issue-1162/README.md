# U05 report-date verification

- [x] Review recovery r4301149179: publish JUnit without suite hostnames, with
  explicit original/published hashes and unchanged actual argv/cwd provenance.
  Verified by eight publication regressions and a byte comparison against the
  original committed XML and execution bindings.
- [x] Review recovery r4301149187: recognize explicit generation provenance;
  ordinary Config Team notes preserve identified dates and conflicts. Nine unit
  cases and a real-XLSX pipeline case failed before the change and passed afterward.
- [x] Review recovery r4301149194: reject blank override reasons before creating
  a run directory. Six CLI regressions cover empty, space-only and tab/newline
  reasons with automatic and explicit output paths, and verify neither output
  parent exists after rejection. The valid audited override case still passes.
- [x] Review recovery r4301168987: count incomplete secondary dates as ambiguous,
  including `2026-01-31 /2026-02-3`. The native before/after proof below records
  the exact implementation change and actual regression results.

Recovery validation: `python -m pytest tests/test_dates.py
tests/pipeline/test_as_of_header_mismatch.py tests/pipeline/test_header_extraction_boundaries.py
tests/test_report_date_evidence_publication.py tests/test_pipeline_run_dir_safety.py
-m 'not slow' -q --tb=short` passed all 110 cases. Repository Black checked 380
files; Ruff passed for all six changed Python files, and mypy passed for the two
changed application modules. Black's multi-file execution stalled in this
sandbox, so each file was checked separately with a shared temporary cache before
the required repository-wide check completed successfully using that verified cache.

Commit handoff: the implementation and verification are complete, but `git add`
failed to create `.git/index.lock` because this run mounts `.git` read-only.
No commit was created.

## Native malformed-secondary-date recovery

`review-malformed-red.*` and `review-malformed-green.*` are fresh executions in
the recovery workspace, with the actual interpreter, argv, cwd, source/test
hashes, console hash, original JUnit hash and published JUnit hash. The test
files and pipeline source are byte-identical across these two runs; only
`dates.py` changes by `review-malformed-fix.patch`. Of 15 selected regressions,
the old implementation produces 11 assertion failures and four passes, with
zero errors or skips. The fixed implementation passes all 15, with zero errors
or skips. `review-malformed-proof.json` binds both execution records, the exact
source hashes and the implementation patch. This is a native before/after fix,
not a claim that the original scope-disconnection proof tested these new cases.

## Original scope verification

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
source/test SHA-256 values, exit code, raw console SHA-256, and original JUnit
SHA-256 where applicable. These execution fields describe the original run and
have not been rewritten for publication.

The published JUnit files omit only `hostname` attributes on suite elements.
`junit_sha256` continues to identify the original report; `junit_publication`
records `original_sha256`, `published_sha256`, the number of removed attributes,
and the explicit `remove-junit-suite-hostname-v1` transformation. All other XML
bytes, including timestamps and failure diagnostics, are preserved. The
repository-specific `python -m tools.publish_report_date_evidence` command
performs this transformation after verifying the original hash and checks the
published hash on repeated invocation. Console logs and their hashes are unchanged.

`acceptance-final.*` covers the U05 cases, real parser/output pipeline,
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

Original run results: 55 acceptance cases and 184 compatibility cases passed, with no
errors or skips. Black checked 292 files, Ruff passed, and mypy passed all 106
source files. `verification.json` records those historical JUnit/log/source bindings;
their source hashes describe that original run, rather than the later recovery edits.
