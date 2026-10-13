# Counter_Risk #1151 — configured PPT refresh selection

The production `_write_outputs` path respects the configured registry: disabled or omitted `ppt_link_refresh` performs zero refresh calls and records SKIPPED with a reason; enabled performs exactly one. All six enabled/disabled/omitted × distribution-enabled/disabled cases verify manifest and data-quality output. Actual refresh failures continue to suppress distribution through existing tests. The registry remains unchanged: the config entries that `load` consumes already expose name, stage and enabled; no redundant accessor is needed.

Commands use the configured Python environment and normal repository `pythonpath`. Raw logs/JUnit are adjacent:

- Original production + new six cases: four disabled/omitted assertion failures, two enabled passes (`refresh-baseline.*`).
- `python -m pytest tests/pipeline/test_monthly_pipeline_ppt_outputs.py tests/outputs -q`: 45 passed, including existing failed-refresh distribution suppression (`refresh-green.*`).
- Final standalone generator suite including disabled global PPT: eight passed (`standalone-green.*`); this adds one new case to the earlier 45 unique tests.
- Guard removal only (`if not ran_master_refresh and refresh_enabled` → `if not ran_master_refresh`), same six-case command: four assertion failures/two passes (`refresh-red.*`). Byte-identical source restoration: six passed (`refresh-restored.*`). SHA256 in `refresh-mutation.json` binds the restoration.
- Focused Ruff, repository Black and production module Mypy pass; logs retained. README documents selection and distribution behavior.

This is bounded local Python/presentation-fixture coverage. Native Windows Office COM execution, hosted CI, provider verdicts, and deployment are not established by these tests. The unchanged native refresher is mocked for deterministic call/status observations. Absolute temporary paths in raw logs identify this run; hashes bind their exact bytes.
