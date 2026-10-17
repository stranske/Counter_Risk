# Issue 1159 local validation evidence

Implementation base: `d3cf9ebb82f80c5c86f6ac5a941470431cd3018b` (origin/main at preflight).
Interpreter: `/opt/anaconda3/bin/python3` (Python 3.12.2); no repository-selected venv exists.

The pipeline passes adjusted data to run-local CPRS reporting workbooks before
screenshot export. Explicit screenshot precedence stays at the existing merge.
Original MOSERS and historical input hashes are checked by the integration test.
The new helper copies unadjusted variants byte-for-byte and snapshots adjusted
All Programs cached values to avoid recalculation undoing the adjustment.

Final local commands (each invoked through the interpreter's `-m pytest`):

- `pytest tests/pipeline/test_cprs_screenshot_generation.py -k adjusted`: 2 passed.
  `verify_break.py` serializes GREEN → original exporter route RED (1 failed,
  1 passed) → byte-identical restore → identical-command GREEN (2 passed).
- `pytest tests/pipeline/test_run_pipeline.py -k screenshot`: 2 passed. These
  real pipeline runs assert exporter CH/FCM cash, historical Cash, totals,
  input hashes and final PPT explicit/generated image selection.
- `pytest tests/pipeline/test_cprs_screenshot_generation.py tests/test_pipeline_screenshot_replacement.py`:
  22 passed, 1 Office skip. Includes unchanged-copy and duplicate/new-row cases.
- `pytest tests/pipeline/test_run_pipeline.py -k optional_input_provenance_hashes`:
  1 passed, including explicit-wins generated-image provenance.
- `pytest tests/pipeline/test_run_pipeline.py -k 'apply_daily_holdings_repo_cash or authoritative_repo_cash'`:
  13 passed; preserves existing cash source, override and duplicate semantics.
- Black, Ruff and Mypy for the edited application/test files pass. Diff check passes.

`verify_pipeline_break.py` additionally replays the original exporter route
through the real full-pipeline CIBC regression and byte-restores it before
rerunning the identical command. Its logs and hash manifest record the results.

Office rendering remains pending, not a local pass. See `OFFICE_HANDOFF.md` for
the opt-in Windows command, input-preservation checks and final-media evidence.
Hosted CI, provider review, normal merge gates, verification and source acceptance
are separate pending gates. No merge/close or CI wait is performed by this opener.

`capability-advice.json` is an advisory snapshot: direct registry lock access was
sandbox-denied. Dispositions are in `capability-disposition.json`; the publication
receipt binds them to the eventual exact PR. `ownership-preflight.json` records
the issue/PR/claim/reservation checks; no prior writer was taken over.

Retained unsuccessful attempts are explicitly labeled: `initial-fixture-failure`
used fake PNG bytes with a now-readable PPT template (fixed by writing a real PNG);
`pipeline-interrupted` records one passing case before interruption. Neither is
counted as final acceptance. Pandas reports optional numexpr/bottleneck version
warnings on this shared interpreter; the focused local gates complete successfully.
`SHA256SUMS.json` binds final source/tests and retained evidence bytes.
