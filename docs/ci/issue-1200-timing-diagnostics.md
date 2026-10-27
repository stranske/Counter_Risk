# Issue #1200: retained Python 3.14 timing diagnostics

Recovered diagnostic evidence for #1200 from [push-to-main run 40344564212, Python 3.14 job 121648074591](https://github.com/stranske/Counter_Risk/actions/runs/40344564212/job/121648074591).

That run did not print a pytest `--durations` table and its metrics step was skipped. The table below ranks **log-derived elapsed intervals**, measured from each test's start log line to its matching xdist result line. All 2,537 unique tests have matching pairs (2,531 passed + 6 skipped), with no negative intervals. These are approximate setup/call and log-delivery intervals, **not pytest's measured phase durations or JUnit totals**.

| Seconds (approx.) | Test |
| ---: | --- |
| 281.306 | `tests/test_pipeline_screenshot_replacement.py::test_office_cash_change_updates_final_ppt_media_preserving_inputs[portable]` |
| 163.907 | `tests/spec/test_macro_spec_fixtures.py::test_macro_spec_range_level_outputs_match_expected_mosers_format` |
| 153.992 | `tests/pipeline/test_run_pipeline.py::test_run_pipeline_writes_expected_outputs_and_manifest` |
| 151.610 | `tests/pipeline/test_run_pipeline.py::test_screenshot_repo_cash_agrees_with_historical_and_totals[zero-override]` |
| 150.665 | `tests/integration/test_cli_run.py::test_cli_run_workflow_mode_writes_manifest_and_data_quality_summary` |
| 146.861 | `tests/pipeline/test_run_pipeline.py::test_screenshot_repo_cash_agrees_with_historical_and_totals[negative-override-explicit-image]` |
| 146.586 | `tests/pipeline/test_run_pipeline.py::test_run_pipeline_manifest_includes_pdf_skip_warning_when_com_unavailable` |
| 146.189 | `tests/pipeline/test_run_pipeline.py::test_screenshot_repo_cash_agrees_with_historical_and_totals[explicit-image]` |
| 141.734 | `tests/pipeline/test_run_pipeline.py::test_screenshot_repo_cash_agrees_with_historical_and_totals[source-cash]` |
| 141.630 | `tests/pipeline/test_monthly_pipeline_ppt_outputs.py::test_final_concentration_slide_precedes_pdf_export[False-True-23]` |
| 141.077 | `tests/pipeline/test_monthly_pipeline_ppt_outputs.py::test_final_concentration_slide_precedes_pdf_export[True-True-24]` |
| 127.060 | `tests/test_web_demo_smoke.py::test_web_demo_artifact_uses_fixture_data_and_disables_chat` |
| 113.763 | `tests/pipeline/test_as_of_header_mismatch.py::test_real_pipeline_parsers_and_outputs_keep_date_conflict_diagnostics` |
| 111.533 | `tests/pipeline/test_run_pipeline.py::test_run_pipeline_invokes_ppt_link_refresh` |
| 110.925 | `tests/pipeline/test_run_pipeline.py::test_run_pipeline_wraps_output_write_errors` |
| 102.522 | `tests/pipeline/test_run_pipeline.py::test_run_pipeline_wraps_manifest_generation_errors` |
| 101.588 | `tests/pipeline/test_run_pipeline.py::test_run_pipeline_passes_as_of_date_and_parsed_inputs_to_historical_update` |
| 99.478 | `tests/pipeline/test_run_pipeline.py::test_run_pipeline_generates_all_programs_mosers_from_raw_nisa_input` |
| 99.390 | `tests/test_web_demo_smoke.py::test_web_demo_rejects_non_fixture_optional_inputs` |
| 92.532 | `tests/pipeline/test_run_pipeline.py::test_run_pipeline_invalid_limits_config_fails_during_limit_breach_stage` |
| 89.543 | `tests/pipeline/test_run_pipeline.py::test_run_pipeline_strict_missing_limit_entities_fails` |
| 89.472 | `tests/pipeline/test_run_pipeline.py::test_run_pipeline_generates_ex_trend_and_trend_mosers_from_raw_nisa_inputs` |
| 88.770 | `tests/pipeline/test_run_pipeline.py::test_run_pipeline_manifest_includes_distribution_static_warning` |
| 86.018 | `tests/pipeline/test_run_pipeline.py::test_run_pipeline_wraps_historical_update_errors` |
| 84.308 | `tests/pipeline/test_run_pipeline.py::test_run_pipeline_warn_mode_writes_mapping_updates_and_completes` |

The retained Python 3.14 JUnit artifact is `gate-coverage-3.14-1` (artifact ID 12662678394). GitHub's connector can retrieve its download reference, but the local execution environment cannot download the ZIP; direct GitHub CLI network access also fails. Downloading that artifact and ranking its JUnit testcase times, or dispatching the existing branch CI workflow with metrics enabled, is still needed for the requested authoritative table. No timing or live-runtime acceptance checkbox is marked complete from these estimates.

Repository test change: added a check that **every** reusable Python CI job retains `slow-test-top: '25'`. The existing metrics test could pass after the primary job lost that setting because it only examined jobs still containing the input. Seven focused tests and Ruff pass; eight in-memory defect probes detect missing/reduced settings across all four jobs without editing protected workflow files.

The branch already contains the suite split and timing inputs. Any further `.github/workflows/ci.yml` changes require an approved `agent-high-privilege` run under the supplied security instructions. Remaining live validation: collect the primary-runtime timing artifact, then inspect every job's start/completion timestamps in a new push-to-main CI run and verify none exceeds 600 seconds.

Formatting verification: all 394 Python files passed individual Black checks,
then the required repository-wide check passed with `BLACK_NUM_WORKERS=1` and
`BLACK_CACHE_DIR=/tmp/counter-risk-black-cache` (394 files unchanged). This avoids
the sandbox's multiprocessing restriction while retaining all formatting checks.

Posting this evidence to #1200 and adding `needs-human` to PR #1201 were blocked:
the GitHub tools require approval, while this run's approval policy is `never`.
