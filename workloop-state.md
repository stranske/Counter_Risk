# Counter_Risk workloop state

## 2026-06-10T20:09:49Z - opener (codex) materialized issue #703

- **Lane:** opener (Codex) from neutral Code workspace.
- **Issue:** stranske/Counter_Risk#703 (priority:normal, repo-review-approved) - align Runner and GUI output folders with the pipeline repeat-run contract.
- **Branch/PR:** `codex/issue-703-output-dir-contract`; PR #704 opened ready-for-review, non-draft, with `agent:codex`, `agents:keepalive`, `autofix`, `priority:normal`, and `repo-review-approved`.
- **Worktree:** `/Users/teacher/.codex/automations/pd-workloop-resume/worktrees/counter-risk-703-output-dir`.
- **Cap/drain preflight:** repaired `stranske/trip-planner#1368` by adding `agents:keepalive`/`agent:retry` and dispatching Gate Followups. Post-repair cap-health classified it as `draining` with fresh Gate evidence; raw opener cap remained below 5.
- **Change:** replaced fixed `_000000` launcher output paths with repeat-run-safe date folders (`YYYY-MM-DD`, then `_1`, `_2`, ...), kept GUI post-run buttons pointed at the actual completed run directory, updated VBA parity source, and refreshed operator/GUI/macro docs.
- **Validation:** `UV_CACHE_DIR=/tmp/uv-cache-pd-workloop uv run pytest tests/test_runner_launch.py tests/test_gui_runner.py tests/test_pipeline_run_dir.py::test_run_directory_creation_same_date_repeat_run_uses_unique_directory_suffix tests/test_runner_vba_module.py tests/test_runner_xlsm_vba_project.py -q` passed (70 passed). `git diff --check` passed. `rg "_000000" src/counter_risk/runner_launch.py src/counter_risk/gui/runner.py` returned no matches.
- **Deliberate break:** temporarily changed `_run_folder_name()` back to `f"{parsed_date.isoformat()}_000000"`; `pytest tests/test_gui_runner.py::test_execute_gui_run_same_date_does_not_produce_fixed_000000_path -q` failed because the result path was `2025-12-31_000000` instead of `2025-12-31_1`. Reverted and reran focused tests green.
- **Post-open evidence:** `pr_opened` relay fired for #704. Cap-health at 2026-06-10T20:11:26Z classified #704 as `draining` with an active Gate run after the latest branch update; raw opener cap remained below 5.
- **Next action:** wait_for_keepalive; keepalive owns CI/review, closer owns merge and verifier/source issue closure.

## 2026-06-10T22:06Z - opener (codex) materialized issue #705

- **Lane:** opener (Codex) from neutral Code workspace.
- **Issue:** stranske/Counter_Risk#705 (priority:normal, repo-review-approved) - add directional baseline checks for treasury and equity concentration metric segments.
- **Branch:** `codex/issue-705-directional-segment-baselines`; worktree `/Users/teacher/.codex/automations/pd-workloop-resume/worktrees/counter-risk-705-directional`.
- **Cap/drain preflight:** raw opener cap below 5. Repaired stale blocker labels on existing opener-owned PR #704; post-repair cap-health classified #704 as draining with fresh Gate/keepalive evidence.
- **Change:** added treasury/equity concentrated scenarios, enforced HHI directional checks, extended priority metrics with `all_programs.treasury.hhi` and `all_programs.equity.hhi`, and refreshed `docs/reports/baseline-coverage.md` from 3/9 (33.3%) to 5/9 (55.6%).
- **Validation:** `pytest tests/baseline/test_directional.py tests/baseline/test_coverage_manifest.py::test_priority_metrics_covered tests/baseline/test_coverage_manifest.py::test_emit_coverage_report -q` passed (10 passed). `BASELINE_REFRESH_REPORT=1 pytest tests/baseline/test_coverage_manifest.py::test_emit_coverage_report -q` passed. `rg "enforce: true" tests/baseline/catalog.yaml | wc -l` returned 8. `git diff --check` passed.
- **Deliberate break:** temporarily changed `treasury_concentrated_raises_hhi` direction to `decrease`; `pytest 'tests/baseline/test_directional.py::test_directional[treasury_concentrated_raises_hhi]' -q` failed with `Economically wrong direction -- treasury_concentrated_raises_hhi: all_programs.treasury.hhi variant=0.860254 decrease control=0.445 -> False`. Reverted before final validation.
- **Next action:** commit/push branch, open ready-for-review PR with `agent:codex`, `agents:keepalive`, `autofix`, `repo-review-approved`, and `priority:normal`; then wait_for_keepalive.

## 2026-05-30T20:32Z - closer (codex) resolved PR #662 review threads

- **Lane:** closer / complex review-thread recovery from neutral Code workspace. Target: [#662](https://github.com/stranske/Counter_Risk/pull/662) for issue [#651](https://github.com/stranske/Counter_Risk/issues/651), branch `codex/issue-651-evidence-provenance`.
- **Audit:** PR was non-draft, issue-linked, `MERGEABLE`, and in scope. Three unresolved Copilot review threads were actionable: avoid a third CPRS-FCM workbook parse for evidence, replace substring-based LangSmith record assertions with structural checks, and parse NDJSON before asserting local evidence keys are not exported.
- **Fix pushed:** commit `9638168` adds `parse_fcm_totals_with_evidence()` so totals and evidence reuse one parsed totals record set; updates `_parse_inputs()` to call it; changes `test_top_exposure_evidence.py` to recursively check key absence; and changes `test_run_pipeline.py` to parse `langsmith-fleet.ndjson` before checking exported keys.
- **Validation:** `python -m pytest tests/pipeline/test_top_exposure_evidence.py tests/pipeline/test_run_pipeline.py::test_run_pipeline_writes_expected_outputs_and_manifest -q` -> 3 passed. `python -m ruff check ...` -> passed. `python -m ruff format --check ...` -> passed.
- **Current state:** evidence comment posted on #662 (`pull/662#issuecomment-4584571266`) and all three review threads resolved. Remote head is `9638168`; `mergeable=MERGEABLE`, `mergeStateStatus=UNSTABLE` because fresh post-push Gate/Backplane/PR meta checks are in progress. Next closer: re-check checks; if green and no new threads, merge #662, apply `verify:compare`, and reopen #651 for verifier sequencing.

## 2026-05-30T20:14Z - opener (codex) materialized issue #651

- **Lane:** opener (Codex) from neutral Code workspace.
- **Issue:** stranske/Counter_Risk#651 (priority:normal, repo-review-approved) - attach Evidence provenance to extracted `top_exposures` facts.
- **Branch/PR:** `codex/issue-651-evidence-provenance`; PR #662 opened ready-for-review, non-draft, with `agent:codex`, `agents:keepalive`, `autofix`, `priority:normal`, and `repo-review-approved`.
- **Cap/drain preflight:** raw cap was below 5. Repaired stale blocker labels on Workflows#2190; Counter_Risk#661, Workflows#2190, Workflows#2192/#662 were draining or freshly waiting on CI, while Trend_Model_Project#5353 remained a scoped product/scope blocker.
- **Change:** added typed manifest Evidence for top exposures, exported CPRS-FCM totals source evidence without changing the public parser DataFrame columns, threaded evidence into `_compute_metrics`, tightened the manifest schema, and documented that evidence remains local to `manifest.json` and out of LangSmith fleet records.
- **Validation:** `python -m pytest tests/pipeline/test_top_exposure_evidence.py tests/pipeline/test_manifest_schema_conformance.py tests/pipeline/test_manifest_provenance.py -q`; parser/MOSERS smoke for NISA parsers and MOSERS workbook parseability; `python -m pytest tests/pipeline/test_run_pipeline.py::test_run_pipeline_writes_expected_outputs_and_manifest -q`; targeted `ruff check` on touched files.
- **Post-open routing:** `pr_opened` relay fired for #662. Initial cap-health lagged on dispatch evidence, so `opener-repair-infra-stalls.py` added `agent:retry` and dispatched Gate Followups. Fresh cap-health saw #662 as draining/fresh async work.
- **Next action:** wait_for_keepalive; keepalive owns CI/review, closer owns merge and verifier/source issue closure.

## 2026-05-30T19:12Z - opener (codex) materialized issue #646

- **Lane:** opener (Codex) from neutral Code workspace.
- **Issue:** stranske/Counter_Risk#646 (priority:normal, repo-review-approved) — replace template placeholder package metadata and remove the stray `src/my_project` package.
- **Branch:** `codex/issue-646-package-metadata`; worktree `/Users/teacher/.codex/automations/pd-workloop-resume/worktrees/counter-risk-646-package-metadata`.
- **Cap/drain preflight:** raw opener cap was 4 (<5). Pension-Data#491, Workflows#2190, and Workflows#2192 were draining with fresh Gate/keepalive evidence; Trend_Model_Project#5353 remained a scoped non-repairable product/scope blocker. Workflows#2159 was dispositioned as already code-supported on `main` but Template still drifted, so targeted maint-68 sync run `26692356766` was dispatched for `stranske/Template`.
- **Change:** set project metadata to `counter-risk`, Counter_Risk URLs, and non-placeholder author/description; removed `src/my_project`, its placeholder test, and the `my_project` first-party Ruff entry; refreshed lock-file provenance comments; added `tests/test_package_metadata.py`.
- **Validation:** `python -m pytest tests/test_package_metadata.py tests/test_dependency_version_alignment.py tests/test_cli.py -q` (6 passed); `python -m ruff check pyproject.toml tests/test_package_metadata.py tests/__init__.py`; `python scripts/sync_test_dependencies.py --verify`; `/tmp/counter-risk-646-venv/bin/python -m pip install --no-deps .` followed by import smoke (`counter_risk` imports, `my_project` raises `ModuleNotFoundError`, dist name `counter-risk`, top_level.txt only `counter_risk`).
- **Post-open repair:** PR #660 opened ready-for-review with `agent:codex`, `agents:keepalive`, `autofix`, `priority:normal`, `repo-review-approved`; `pr_opened` event fired. Initial cap-health reported `needs-dispatch-evidence`; `opener-repair-infra-stalls.py` added `agent:retry` and dispatched Gate Followups. CI exposed a bounded dependency-validator issue from importing `setuptools` in the new test, so the test was switched to stdlib `pkgutil` package discovery and repushed.
- **Next action:** wait_for_keepalive; closer owns post-merge verifier/source issue closure.

## 2026-05-30T06:14Z - opener (codex) quick-recovered PR #654 lint failure

- **Lane:** opener quick-recovery during cap-drain sweep; raw opener cap reached after Inv-Man-Intake#481 opened.
- **PR:** stranske/Counter_Risk#654, branch `codex/issue-644-runtime-dependencies`, head before recovery `359eb17`.
- **Failure evidence:** Gate run `26676332350` failed `Python CI / lint-ruff` on two branch-local Ruff `SIM103` violations: `scripts/langchain/followup_issue_generator.py:889` and `scripts/langchain/issue_formatter.py:162`.
- **Change:** simplified both placeholder-check helper tails to return the regex condition directly.
- **Validation:** `python -m ruff check scripts/langchain/followup_issue_generator.py scripts/langchain/issue_formatter.py`; `python -m pytest tests/test_followup_issue_generator_checklist_placeholders.py tests/test_issue_formatter_checklist_placeholders.py`.
- **Next:** push recovery commit and wait for fresh Gate/keepalive evidence.

## 2026-05-30T05:00Z - opener (codex) materialized issue #644

- **Lane:** opener (Codex), baton.round=12.
- **Issue:** stranske/Counter_Risk#644 (priority:high, repo-review-approved) — declare pandas as a runtime dependency and reconcile runtime dependency declarations.
- **Branch:** `codex/issue-644-runtime-dependencies` (matches registry `codex/issue-*` prefix).
- **Worktree:** `/Users/teacher/.codex/automations/pd-workloop-resume/worktrees/counter-risk-issue-644`.
- **Cap/drain preflight:** repaired Counter_Risk#652 by adding `agent:retry` and dispatching Gate Followups; post-repair cap-health classified it as `draining` with a pending Gate run. Raw cap remained below 5.
- **Change:** added `pandas>=2.3,<4` to runtime `[project.dependencies]`, aligned `requirements.txt` runtime floors with `pyproject.toml`, updated pandas/Pillow lock snapshots, and added `tests/test_runtime_dependencies_declared.py` as the failing-first guard for runtime imports declared only in dev extras.
- **Validation:** `python -m pytest tests/test_runtime_dependencies_declared.py tests/test_dependency_version_alignment.py` passed (2 tests). `/tmp/counter-risk-issue-644-venv/bin/python -m pip install -e .` passed and installed from this worktree; installed import check reported `counter_risk` from this worktree and pandas `3.0.3`; CLI help worked. Fixture replay could not run because the proprietary `fixtures/` directory is absent from the checkout, failing before parser import with `FileNotFoundError`.
- **PR:** #654 OPEN, ready-for-review (not draft), base `main`; labels verified as `agent:codex`, `agent:retry`, `agents:keepalive`, `autofix`, `repo-review-approved`, and `priority:high`.
- **Post-open routing:** initial cap-health saw #654 needing dispatch evidence; `opener-repair-infra-stalls.py` added `agent:retry` and dispatched Gate Followups. Final cap-health at 2026-05-30T04:54:57Z classified #654 as `draining` with an active Gate run. #652 also classified as `draining`, and its stale `needs-human` label was gone.
- **Relay:** `pr_opened` event written with `active.source_repo=stranske/Counter_Risk`, `active.source_issue=644`, `active.source_pr=654`, `active.next_action=wait_for_keepalive`.
- **Next action:** wait_for_keepalive (keepalive workflow + Codex runner own CI/review from here; closer owns post-merge verify/close).
