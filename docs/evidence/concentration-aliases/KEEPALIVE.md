# Acceptance recheck, 2026-10-13

The unchecked task list was stale: the canonical reshaper and rollup were already
implemented in `06d536b`. This round strengthens the production reshaper regression
for case aliases, all five asset classes, total, unknown peers, signed values, and
multiple variants. CPRS-FCM parser docstrings now explicitly state that source
spelling is retained and registry identity is resolved downstream.

The rollup returns group-level scalar metrics, with no counterparty display column.
Display labels and their deterministic source order remain in the reshaped exposure
rows; the regression asserts those rows exactly. No output columns were added.

## Verified tasks

- [x] Emit registry canonical keys alongside display labels in the production reshaper.
- [x] Consolidate gross magnitudes by canonical identity within each group and preserve source display order.
- [x] Retain raw parser labels and document downstream identity resolution.
- [x] Cover registered/case aliases, unrelated/unknown entities, mixed signs, more than ten entities, and group boundaries.
- [x] Verify workbook parser to CSV, manifest, and native PowerPoint table against a hand calculation.
- [x] Verify corrected PowerPoint values and table-before-PDF-export ordering in all three option combinations.
- [x] Document registry canonical identity in the CSV documentation.

## Acceptance evidence

Every pytest command below uses `-m "not slow"`; logs include complete commands'
test selection and JUnit accompanies each suite.

- [x] `python -m pytest tests/compute/test_concentration_metrics.py -k alias -m "not slow"`: **12 passed**, 44 deselected. See [log](keepalive-alias-green.log) and [JUnit](keepalive-alias-green.xml).
- [x] `python -m pytest tests/pipeline/test_run_pipeline.py -k concentration -m "not slow"`: **14 passed**, 182 deselected. See [log](keepalive-pipeline-green.log) and [JUnit](keepalive-pipeline-green.xml).
- [x] Variant and segment separation is asserted in `test_registered_aliases_preserve_variant_and_segment_boundaries` and the new `test_alias_reshaper_emits_identity_for_every_segment_and_variant`.
- [x] Replacing only rollups with original production fails **all 12 alias tests**; byte-identical restoration passes **all 12**. See [RED](keepalive-rollups-red.log), [restored GREEN](keepalive-rollups-restored-green.log), their JUnit files, and [mutation receipt](keepalive-mutation.json).
- [x] `rg -n "canonical" docs/concentration_metrics.md` finds the registry identity statement. See [output](keepalive-canonical.log).
- [x] Evidence and corrected report observations are retained here. [Observed CSV/manifest/PPT values](keepalive-report-observations.json) were extracted from actual artifacts produced by `test_concentration_alias_parser_csv_manifest_ppt`, then checked against the canonical hand calculation. Citibank 60 plus Citigroup -40 has gross exposure 100: Equity/total HHI and both shares are 1.0; other segments are zero. PPT renders `100.00%`, `100.00%`, `1.0000` for the nonzero groups. See the [artifact-producing test log](keepalive-report-artifacts.log).

Additional verification:

- `python -m pytest tests/compute/test_concentration_metrics.py tests/parsers/test_cprs_fcm.py -m "not slow"`: **71 passed** (56 concentration and 15 parser tests), [log](keepalive-compute-parser-green.log) and [JUnit](keepalive-compute-parser-green.xml).
- `python -m pytest tests/pipeline/test_monthly_pipeline_ppt_outputs.py::test_final_concentration_slide_precedes_pdf_export -m "not slow"`: **3 passed**, [log](keepalive-ppt-green.log) and [JUnit](keepalive-ppt-green.xml). The export fixture records sequencing; native Office COM export remains unverified on Linux.
- Black 26.10.0 formatted both touched Python files and checked all **370** repository Python files using `--check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .`; [log](keepalive-black.log). The sandbox blocks multiprocessing socket binding and thread wakeups. The successful Black CLI invocation used one worker and a 50 ms event-loop heartbeat, leaving parsing, formatting, file selection, and check behavior unchanged.
- Touched-file Ruff and `git diff --check` pass; [Ruff log](keepalive-ruff.log).

All 21 existing hashes in `SHA256.json` verified before this recheck. Original
evidence remains unchanged. `keepalive-SHA256.json` binds this round's evidence.

## Publication blocker

The checkout's `.git` mount is read-only, so staging here fails with
`Unable to create .../.git/index.lock: Read-only file system`. An isolated bare
repository under `/tmp/concentration-alias-commit.git` contains the meaningful
source/test/evidence commit, with this checkout's HEAD as its parent. The verified
import bundle is `/tmp/concentration-alias-acceptance.bundle`.

The GitHub connector also rejected `github_create_tree` with
`MCP tool call requires approval, but approval policy is never`. No remote source
commit or PR-body update was made. The verified acceptance results above describe
the local implementation. A runner with Git write access must import and publish
the commit before updating the PR's stale checkboxes.

- [ ] Publish the commit and link this round's evidence from PR #1150.
