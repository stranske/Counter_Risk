# Counter_Risk #1151 — configured PPT refresh selection

The production `_write_outputs` path respects the configured registry: disabled or omitted `ppt_link_refresh` performs zero refresh calls and records SKIPPED with a reason; enabled performs exactly one. All six enabled/disabled/omitted × distribution-enabled/disabled cases verify manifest and data-quality output. Actual refresh failures continue to suppress distribution through existing tests. The registry remains unchanged: the config entries that `load` consumes already expose name, stage and enabled; no redundant accessor is needed.

Commands use the configured Python environment and normal repository `pythonpath`. Raw logs/JUnit are adjacent:

- Original production + new six cases: four disabled/omitted assertion failures, two enabled passes (`refresh-baseline.*`).
- `python -m pytest tests/pipeline/test_monthly_pipeline_ppt_outputs.py tests/outputs -q`: 45 passed, including existing failed-refresh distribution suppression (`refresh-green.*`).
- Final standalone generator suite including disabled global PPT: eight passed (`standalone-green.*`); this adds one new case to the earlier 45 unique tests.
- Guard removal only (`if not ran_master_refresh and refresh_enabled` → `if not ran_master_refresh`), same six-case command: four assertion failures/two passes (`refresh-red.*`). Byte-identical source restoration: six passed (`refresh-restored.*`). SHA256 in `refresh-mutation.json` binds the restoration.
- Focused Ruff, repository Black and production module Mypy pass; logs retained. README documents selection and distribution behavior.

This is bounded local Python/presentation-fixture coverage. Native Windows Office COM execution, hosted CI, provider verdicts, and deployment are not established by these tests. The unchanged native refresher is mocked for deterministic call/status observations. Absolute temporary paths in raw logs identify this run; hashes bind their exact bytes.

Follow-up verification strengthens the tests without changing the existing production guard. The selection matrix now also exercises the legacy fallback with no refresh generator returned by the registry. Assertions read the written `manifest.json` and `DATA_QUALITY_SUMMARY.txt`; the existing failed-refresh test checks that those artifacts report failure and suppress distribution, rather than reporting an intentional skip.

- [x] Disabled and omitted registrations make zero refresh calls, return SKIPPED with a reason, and write `master.skipped_reason` and `PPT_LINK_REFRESH_SKIPPED` (`followup-green.*`, 12 passed).
- [x] Enabled registrations make exactly one call, both through the generator and the legacy fallback (`followup-green.*`).
- [x] Failed-refresh distribution suppression and all eight standalone-generator tests pass (`followup-regressions.*`, nine passed).
- [x] Removing only the fallback guard fails all eight disabled/omitted zero-call assertions; byte-identical restoration passes all 12 cases (`followup-red.*`, `followup-restored.*`, `followup-mutation.json`).
- [x] `rg -n "ppt_link_refresh" README.md` confirms the documented disabled/omitted skip behavior at line 54.

Follow-up commands include `-m "not slow"`. `followup-SHA256.json` records hashes for the follow-up logs, JUnit, mutation record, and source/test files. The repository Black check passed for all 370 files with the required CLI arguments. Its temporary runner uses `BLACK_NUM_WORKERS=1` and schedules an event-loop tick every 0.05 seconds: the sandbox blocks the default process-pool socket and does not wake the event loop after thread completion. The runner invokes Black's normal CLI without altering formatting or file selection. Focused Ruff also passed. The broader existing pipeline/standalone suite passed all 33 tests before the test additions.

Historical hosted-run delivery limitation (superseded by the closer recovery below): the sandbox mounts `.git` read-only, so staging and committing fail when Git creates `.git/index.lock`. GitHub connector commit creation, the `needs-human` label, and a blocker comment were also denied because they require approval while this run's approval policy is `never`. No remote changes were made. The saved changes require a writable Git environment or approved connector writes to commit. PR #1152 was verified open and ready for review at head `a8077e1413d63ef103aee71edba0fbb6de771879`.

## Closer integration recovery — 2026-10-13

The hosted writer completed and its saved follow-up changes were committed as `022463ce7e80ddfea509ec133df30b6abd73ef37`. The closer rebased those existing commits onto main after alias-concentration PR #1150 merged. The sole conflict was the adjacent `typing.Any` and `unittest.mock.Mock` imports in the pipeline test; both are retained. No sandbox approval or human Git repair remains necessary. Original raw logs, JUnit and hash manifests are preserved as historical evidence.

Fresh combined refresh/pipeline/concentration/rollup regression results are recorded in the PR recovery comment and external closer receipt, together with Black, Ruff, Mypy and source/test whitespace validation. Raw historical failure logs contain their original whitespace; they are intentionally not reformatted. Native Office execution and durable provider comparison remain separate acceptance gates. Every recovery push requires fresh hosted checks and the full seven-minute review floor at its exact head.
