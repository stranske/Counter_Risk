Check date: 2026-11-06
Outcome 1: both shipped XLSM archives have parseable CFB/MS-OVBA module streams and RunnerLaunch equals committed source; D5 discovery and I5 guidance must additionally be observed in Windows Excel.
Command: /opt/anaconda3/bin/python3 -m pytest tests/test_runner_workbook.py tests/test_runner_vba_module.py tests/test_runner_launch.py tests/test_build_xlsm.py tests/test_extract_vba_modules.py -q (plus focused sync/CLI tests).
Windows command: open Runner.xlsm in Windows Excel from an unrelated CWD, click D5 and I5, inspect discovery output and documented GUI guidance cell/message.
Stop rule: at most 3 repair attempts per printed failure, 75 minutes total. Stop on either bound and report first broken step; ask should I stop.
Blocking/drainable: Windows Excel unavailable locally / code, artifact validation, focused tests and current-head dispositions remain drainable. No merge or thread resolution in this seat.

## Observed outcome

Outcome 1 = FAIL. The shipped project declares CFB version 4 with 512-byte
sectors (version 4 requires 4096-byte sectors). It has no valid FAT/directory.
`Runner.xlsm`, the template, and `assets/vba/vbaProject.bin` remain unchanged.
No signature-only or readable-source test qualifies them as executable.

The exporter now uses Windows Excel COM on a temporary copy of a genuine input
workbook. It disables macro execution during opening, imports only RunnerLaunch,
preserves project references, saves, extracts, checks all unrelated module source,
then atomically replaces the selected project output. Selected paths are absolute
before subprocess invocation; both diagnostic streams survive failures. This
Windows path has NOT been executed here (local platform darwin, no win32com).
An Excel-saved input workbook is required; passing the existing invalid workbook
fails before Excel starts. This is an explicit remaining delivery dependency.

The independent Excel-saved test fixture is from XlsxWriter (see its adjacent
provenance and BSD license). It is not embedded into the shipped artifacts.
Tests demonstrate five declared module streams, decompression, malformed input
rejection, a changed compressed handler body despite unchanged cached text,
selected-path forwarding and preservation of existing output on export failure.
The read-only parser validates supported structure and source; it does not prove
VBA compilation, macro execution, or full support for every MS-OVBA extension.

## Focused validation (2026-11-06)

Interpreter: `/opt/anaconda3/bin/python3` (no selected repository venv found).
No dependency pins or lockfiles changed. No full suite run.

Command:

```text
/opt/anaconda3/bin/python3 -m pytest tests/test_runner_workbook.py tests/test_runner_vba_module.py tests/test_runner_launch.py tests/test_build_xlsm.py tests/test_extract_vba_modules.py tests/test_vba_project_sync.py tests/test_cli_config_resolution.py -q
```

Final output: `16 failed, 104 passed in 2.11s`.
Every remaining failure reaches `ValueError: Invalid CFB version/sector size`
for the existing shipped pseudo-project. The named suite has NOT passed.

Additional focused command:

```text
/opt/anaconda3/bin/python3 -m pytest tests/test_vba_project_sync.py tests/test_cli_config_resolution.py tests/test_build_xlsm.py -q
```

Output: `1 failed, 30 passed in 1.19s`; the single failure is the built-workbook
actual-module assertion against the same invalid project. CLI precedence,
installed layout, structural XML names/IDs/formatting, unsupported-input
preservation, fixture extraction, and export boundary regressions passed.

Black formatted the changed Python files; `git diff --check` printed nothing.
Black emitted a Python 3.12 versus configured Python 3.13 parsing warning; it
exited successfully. No Ruff formatter was used.

## Literal I5 removal / restoration

Removed exactly this source entry from `scripts/build_runner_workbook.py`:

```python
RunnerActionButton("I5", "Ask about this run", "AskAbout_Click", 9),
```

Ran `/opt/anaconda3/bin/python3 -m pytest tests/test_runner_workbook.py -q`.
Output: `8 failed, 11 passed in 1.60s`, including:

```text
FAILED tests/test_runner_workbook.py::test_runner_builder_defines_i5_ask_about_action
AssertionError: I5 RunnerActionButton is missing from builder
```

Restored the literal entry. Ran:

```text
/opt/anaconda3/bin/python3 -m pytest tests/test_runner_workbook.py -q -k test_runner_builder_defines_i5_ask_about_action
```

Output: `1 passed, 18 deselected in 0.21s`.
The full restored workbook suite still has seven invalid-project failures;
this isolated pass is NOT a claim of the requested full-suite red/green outcome.
Workbook regeneration is rejected before replacing output because the input
project is invalid. No validation bypass was used for the removal experiment.

## Windows Excel smoke check

NOT RUN. Requires Windows Excel and genuine saved VBA artifacts. After generating
and embedding a real project with the canonical source and existing required
modules, open both artifacts from an unrelated CWD. D5 must invoke discovery;
I5 must display and write the documented `Use counter-risk gui` guidance.
Neither source inspection nor headless tests substitutes for these observations.

## Review handoff

The live API reported 17 unresolved threads, rather than the supplied count of
13. Current-head replies distinguish fixed code, source-only existing fixes,
and the blocked executable-artifact requirement. No thread resolution or merge
is performed by this seat. The delivery lane must retain the executable-artifact
and Windows-smoke gaps; green CI at an earlier head was not acceptance evidence.
