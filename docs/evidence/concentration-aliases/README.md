# Counter_Risk #1149: registered alias concentration proof

Base: `dc116f2a56769b61f33169b9836dc2e6839f81f9`.
Production changes resolve registry identity before grouping magnitudes; source labels and group boundaries remain intact. No registry entries, parser economics, limit monitoring, or output schemas changed.

## Reproduction and results

Use the Python 3.12 interpreter from the repository root (this run used `/opt/anaconda3/bin/python3`).

- `python3 -m pytest tests/compute/test_concentration_metrics.py -k alias -q -o addopts=` on original production: 9 assertion failures. `baseline-red.log/xml` retain the actual baseline.
- `python3 -m pytest tests/compute/test_concentration_metrics.py -q -o addopts=`: 53 passed.
- `python3 -m pytest tests/compute tests/test_normalize.py tests/test_normalization_registry_first.py tests/test_name_registry.py tests/ppt/test_concentration_table.py -q -o addopts=`: 411 passed.
- `python3 -m pytest tests/pipeline/test_run_pipeline.py -k 'concentration or exposure_builders' -q -o addopts=`: 27 passed,169 deselected. The real CPRS-FCM workbook parser preserves Citibank60/Citigroup-40; CSV, on-disk manifest, and native PPT table agree on HHI1 and both shares1 for Equity/total. Zero-valued segments stay0.
- `python3 -m pytest tests/pipeline/test_monthly_pipeline_ppt_outputs.py::test_final_concentration_slide_precedes_pdf_export -q -o addopts=`: all3 cases passed in175.10s. Production pipeline's CSV/manifest/table use the corrected values, optional-table disablement preserves the manifest, and PDF export observes the final table. The platform-dependent PDF COM backend is replaced by a recording fixture, so this is portable pipeline sequencing proof, not native Office COM verification.
- Source mypy: no issues in2 source files. Ruff, Black, and `git diff --check` passed for all touched Python files.

## Independent production mutations

`mutations.json` binds each production path, command, mutant digest, original/restored digest and exit code. Replacing the rollups implementation with the original baseline fails all6 registered-alias portfolio cases (RED1); exact restoration passes6 (GREEN0). Replacing only the production reshaper's canonical identity with its raw display label fails its named identity regression (RED1); exact restoration passes1 (GREEN0). Both restored files are byte-identical to their pre-mutation contents. Raw logs and JUnit accompany each pair.

Coverage is bounded to these local contracts. Hosted CI, review, provider acceptance, deployment, and native Office integration remain UNKNOWN/pending. Final PR head must independently satisfy complete expected/required checks, zero active review threads, and the seven-minute review floor before delivery.
