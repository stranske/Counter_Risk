Repo Cash adjustments previously reached metrics and historical Excel while CPRS screenshots read the original workbook. Screenshot exports now use run-local reporting snapshots populated from the adjusted Repo rows and FCM totals. Operator inputs remain untouched, unadjusted variants are byte-identical copies, and explicit screenshot inputs retain precedence.

Closes #1159

Validation: named adjusted/export-boundary gate passes with a serialized original-route assertion failure and byte-identical restoration; the named full-pipeline screenshot gate passes (2 cases), and its original-route control fails before byte-identical restoration. Latest committed verification (`c312019`): focused generation/replacement suites 25 passed, 1 Windows Office skip; adjusted gate 5 passed, original-route control 4 failed / 1 passed, restored gate 5 passed; full-pipeline screenshot gate 2 passed. See `docs/evidence/issue-1159/keepalive-2026-10-17/`. Provenance: 1 passed. Existing Repo Cash semantics: 13 passed. Black, Ruff, Mypy and diff checks pass. Console logs, valid JUnit, mutation scripts and SHA-256 bindings are in `docs/evidence/issue-1159/`.

Local follow-up: the shared final-deck smoke now also runs with a cash-reading portable renderer and writes a renderer-labelled JSON evidence report. Portable smoke: 1 passed; native Office: 1 skipped on Linux. Existing screenshot suites: 25 passed; full-pipeline cash agreement/explicit precedence: 2 passed. Evidence and a reconciled PR body are in `docs/evidence/issue-1159/office-portable/`.

Windows Office final-render acceptance is **pending**. The opt-in smoke is implemented; `docs/evidence/issue-1159/OFFICE_HANDOFF.md` gives the command and retained artifacts. Local PNG-export doubles prove data wiring, not native rendering. Adjusted reporting snapshots freeze cached values before overlay so Office cannot recalculate away the adjustment. No COM exporter or slide geometry changes.

Capability advisor: `advice:365e87490d54` recommended deliberate-break verification with `dispatch_ready=false`. Declined the gated `local_verify.py` invocation and used a serialized manual causal proof instead. Codemod campaign and dispatch-based runtime checks do not apply. Shared-registry lock access was sandbox-denied; the identical advisor CLI used a temporary registry snapshot. The exact PR binding is recorded in the publication receipt. CI, provider review, merge and native source acceptance remain pending; this opener does not wait for them.

## Tasks

- [x] Add a helper in `src/counter_risk/pipeline/run.py` that writes the adjusted CPRS-CH/CPRS-FCM reporting state (from `parsed_by_variant` after `src/counter_risk/pipeline/run.py:1142`) into a run-local workbook under `run_dir`.
- [x] Change the `_generate_cprs_screenshot_inputs` signature (`src/counter_risk/pipeline/run.py:3134`) and its call site (`src/counter_risk/pipeline/run.py:583`) to take that run-local workbook path instead of `getattr(config, workbook_field)`.
- [x] Keep the explicit-wins merge at `src/counter_risk/pipeline/run.py:588` unchanged so configured `screenshot_inputs` retain precedence, and keep the no-override path rendering as today.
- [x] Update `tests/pipeline/test_cprs_screenshot_generation.py` (`test_generates_screenshot_for_each_configured_variant_and_table`, :41) so the faked exporter records the workbook handed to it and asserts it contains the adjusted CIBC cash amount.
- [x] Add a regression in `tests/pipeline/test_run_pipeline.py` (near :781) that changes an authoritative Repo Cash amount and asserts the exporter-bound workbook, historical Cash row and totals carry the same value; it must fail on the original-workbook route.
- [x] Add a Windows Office smoke check in `tests/test_pipeline_screenshot_replacement.py` (marked for the Office environment) that a cash change alters the embedded CPRS PNG in the final PPT and original input hashes are unchanged.

## Acceptance Criteria

- [x] `pytest tests/pipeline/test_cprs_screenshot_generation.py -k adjusted` passes and the same test fails against the current `src/counter_risk/pipeline/run.py` route.
- [x] `pytest tests/pipeline/test_run_pipeline.py -k screenshot` passes, asserting exporter input, historical Cash output and totals agree on a changed Repo Cash amount.
- [ ] The Office smoke test (`tests/test_pipeline_screenshot_replacement.py`) shows the final master/distribution PPT media differs after a cash change and the SHA-256 of the original input workbooks is unchanged (platform-handoff brief if not runnable locally).
- [x] A no-override run and a run with explicit `screenshot_inputs` keep their current outputs (existing tests in `tests/pipeline/test_cprs_screenshot_generation.py` and `tests/test_pipeline_screenshot_replacement.py` pass).
- [x] Deliberate-break gate: after adding the scope-specific regression in `tests/pipeline/test_cprs_screenshot_generation.py`, temporarily disconnect its corresponding Scope change at `src/counter_risk/pipeline/run.py`; that regression must fail on the described behavior. Restore the change and rerun it successfully, capturing both outcomes.

<!-- pr-preamble:start -->
<!-- meta:issue:1159 -->
> **Source:** Issue #1159

Closes #1159

<!-- pr-preamble:end -->

<!-- auto-status-summary:start -->
## Automated Status Summary
#### Scope
`README.md` ("What the pipeline produces", "Repo Cash Source Configuration") and `docs/PRODUCT_CONTRACT.md` (C4) promise consistent Excel and PowerPoint outputs that honor authoritative Repo Cash sources and overrides. `src/counter_risk/pipeline/run.py:1142` applies Repo Cash to the parsed totals and the CPRS-CH records (feeding the historical Cash sheet via `src/counter_risk/outputs/historical_workbook.py:53`), but `src/counter_risk/pipeline/run.py:583` then calls `_generate_cprs_screenshot_inputs` (`:3134`) with only `runtime_config`. That function exports the original configured MOSERS workbook via `export_worksheet_range_as_png`, so the slide images never contain the cash adjustment. A read-only probe injected CIBC cash=1234567 through the real cash function and captured the export boundary: adjusted records held CIBC=1234567, while both screenshot calls read the unmodified fixture. Operators would send a PPT whose CPRS tables disagree with the Excel outputs. Office rendering was not run in the probe.

Current source readback: `src/counter_risk/pipeline/run.py:458` at `117fc794902140844ec178e015ff05a4db1bd142` (file SHA-256 `f835664f465c1ff1eee49b2de1dbaec40133c416f56ebf64b03ec47856f63b0b`). Earlier detailed line ranges and reproductions retain their reviewed-commit provenance; intervening anchor changes were checked for relevance.

#### Tasks
- [x] Add a helper in `src/counter_risk/pipeline/run.py` that writes the adjusted CPRS-CH/CPRS-FCM reporting state (from `parsed_by_variant` after `src/counter_risk/pipeline/run.py:1142`) into a run-local workbook under `run_dir`.
- [x] Change the `_generate_cprs_screenshot_inputs` signature (`src/counter_risk/pipeline/run.py:3134`) and its call site (`src/counter_risk/pipeline/run.py:583`) to take that run-local workbook path instead of `getattr(config, workbook_field)`.
- [x] Keep the explicit-wins merge at `src/counter_risk/pipeline/run.py:588` unchanged so configured `screenshot_inputs` retain precedence, and keep the no-override path rendering as today.
- [x] Update `tests/pipeline/test_cprs_screenshot_generation.py` (`test_generates_screenshot_for_each_configured_variant_and_table`, :41) so the faked exporter records the workbook handed to it and asserts it contains the adjusted CIBC cash amount.
- [x] Add a regression in `tests/pipeline/test_run_pipeline.py` (near :781) that changes an authoritative Repo Cash amount and asserts the exporter-bound workbook, historical Cash row and totals carry the same value; it must fail on the original-workbook route.
- [x] Add a Windows Office smoke check in `tests/test_pipeline_screenshot_replacement.py` (marked for the Office environment) that a cash change alters the embedded CPRS PNG in the final PPT and original input hashes are unchanged.

#### Acceptance criteria
- [x] `pytest tests/pipeline/test_cprs_screenshot_generation.py -k adjusted` passes and the same test fails against the current `src/counter_risk/pipeline/run.py` route.
- [x] `pytest tests/pipeline/test_run_pipeline.py -k screenshot` passes, asserting exporter input, historical Cash output and totals agree on a changed Repo Cash amount.
- [ ] The Office smoke test (`tests/test_pipeline_screenshot_replacement.py`) shows the final master/distribution PPT media differs after a cash change and the SHA-256 of the original input workbooks is unchanged (platform-handoff brief if not runnable locally).
- [x] A no-override run and a run with explicit `screenshot_inputs` keep their current outputs (existing tests in `tests/pipeline/test_cprs_screenshot_generation.py` and `tests/test_pipeline_screenshot_replacement.py` pass).
- [x] Deliberate-break gate: after adding the scope-specific regression in `tests/pipeline/test_cprs_screenshot_generation.py`, temporarily disconnect its corresponding Scope change at `src/counter_risk/pipeline/run.py`; that regression must fail on the described behavior. Restore the change and rerun it successfully, capturing both outcomes.

<!-- auto-status-summary:end -->
