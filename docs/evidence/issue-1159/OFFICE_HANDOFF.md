# Windows Office handoff — issue 1159

Pending: native Excel/PowerPoint rendering is unavailable on the current Linux
runner (and was unavailable on the original macOS validation seat).
The operator target supports COM; this is not evidence that this smoke has run.

On an already configured Windows Office test machine, use its explicitly selected
Python environment and run from the PR checkout:

```powershell
$env:COUNTER_RISK_OFFICE_SMOKE = "1"
python -m pytest tests/test_pipeline_screenshot_replacement.py -m "office and not slow" -s --basetemp=office-1159-evidence --junitxml=office-1159.xml
```

The opt-in is required because the test launches installed Excel and PowerPoint.
Run it in the requesting human-visible task context. If the machine needs any
administrator, privacy, security, or helper approval, first explain the exact
executable, publisher (if verified), requested access, persistence, and decline
behavior in that chat; do not grant or bypass unexplained prompts.

The smoke makes two complete real pipeline runs using different authoritative
CIBC cash amounts (1234567 and 7654321), without mocking the exporter or refresh.
It requires both final Master and Distribution PPT files, extracts their slide 1
(CH) and slide 2 (FCM) embedded PNGs, and compares decoded pixels across runs so
changes in PNG metadata or compression alone cannot satisfy the cash-change
assertion. It prints media
SHA-256 values and verifies all six original XLSX input hashes remain unchanged
after each run. Fixture archives are copied, never edited. Retain the XML,
console output, both run directories, reporting XLSX files, and decks.

A skipped Office test is not a pass. Native rendering remains unchecked until
this command completes with one passing test on Windows and the evidence is
retained. The platform-handoff brief satisfies only the documented local fallback.

The local regression uses a recording PNG exporter and real parsing, Repo Cash,
historical writing, totals computation, and PPT replacement. That establishes
pipeline data wiring and explicit screenshot precedence, not Office rendering.
No-override reporting copies are byte-identical to their source workbooks;
adjusted All Programs copies are snapshot workbooks whose cached source values
are frozen before adjusted Repo rows and FCM totals are written. Source workbooks,
cash-source precedence, COM exporter, and slide geometry are unchanged.
