# Runner action controls — issue 1183

D5 binds `DryRunDiscovery_Click` and I5 binds `AskAbout_Click`; existing seven
control IDs/macros remain unchanged. Discovery uses All Programs configuration,
selected month and current settings JSON, with the existing launch/error handling.
Ask-about displays the selected run folder and names `counter-risk gui` for runner
controls; it does not invoke a provider or imply a native Excel Q&A interface.

Validation used the repository-selected `.venv/bin/python`:

```
python -m pytest tests/test_runner_workbook.py tests/test_runner_vba_module.py tests/test_extract_vba_modules.py tests/test_build_xlsm.py tests/test_vba_runnerlaunch_signature.py tests/spec/test_macro_spec_doc.py -q
```

- Updated expectations against the original workbook: 3 failed, 10 passed.
- Removed I5 from the builder and regenerated Runner.xlsm: workbook suite fails.
- Exact-byte restoration of builder and workbook: all 49 focused tests pass.
- Workbook restored SHA-256: b367792fff6a82add4eae748b6a5e4f71387b6580d15d216eb186ab6e4f474c3.

Raw transcripts are adjacent. These verify OOXML bindings and the existing readable
VBA source fixture/mirror. Its OLE-signature prefix and source text do not establish
a compiled executable VBA project. Windows Excel compilation/click testing remains
an unverified release check under `docs/RELEASE_CHECKLIST.md`; no COM helper or
application was launched during this headless change.
