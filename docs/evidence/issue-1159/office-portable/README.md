# Office smoke follow-up

Base: `c312019`. Reviewed both recent implementation commits (`832b093` and
`c312019`) before changing the smoke test. The run-local reporting implementation
and the adjusted exporter regression are already present. The previous
deliberate-break proof's source and regression SHA-256 values still match this
checkout, including its byte-identical restoration.

The existing native Office smoke now shares its assertions with a portable case.
The portable renderer reads CIBC cash from the workbook handed to the exporter
and draws that value into a PNG. Both cases check that the final Master and
Distribution decks embed the generated CH/FCM images, compare decoded pixels
after changing authoritative cash, and verify all six original XLSX hashes after
each run. The JSON report explicitly identifies the renderer.

Verified reconciliation of the supplied acceptance checklist:

- [x] Adjusted exporter gate: 5 passed (`adjusted.log`).
- [x] Pipeline cash agreement and explicit screenshot precedence: 2 passed
  (`pipeline-screenshot.log`).
- [x] Existing no-adjustment and screenshot replacement behavior: 25 passed
  (`existing-screenshots.log`).
- [x] Deliberate-break evidence matches the current source and regression;
  see `../keepalive-2026-10-17/break-proof.json` and its green/red/restored logs.
- [x] Local Office fallback: updated `../OFFICE_HANDOFF.md` with the native
  command, artifacts, JSON evidence, and portable verification command.
- [ ] Native Office execution: unavailable on Linux; the Office parameter skips.

New smoke command:

```text
pytest tests/test_pipeline_screenshot_replacement.py -k cash_change -m "not slow" --basetemp=/tmp/counter-risk-cash-media --junitxml=/tmp/counter-risk-cash-media.xml
```

Result: **1 passed, 1 skipped, 12 deselected** in 189.03 seconds.
`portable-smoke.xml` records the outcome. `cash-media-evidence.json` contains
the two cash amounts, six unchanged input SHA-256 values and changed hashes for
all four delivered slide images. It identifies `portable-test-double` and is
not native rendering evidence. Complete run artifacts remain under
`/tmp/counter-risk-cash-media/` on this execution seat.

Black's required repository-wide command passes for all 379 files (`black.log`).
The sandbox denies default process workers and can stall event-loop wakeups.
The successful command used `BLACK_NUM_WORKERS=1` and a temporary external
`sitecustomize.py` that schedules an event-loop timer every 50 ms. Formatting
rules, source selection, and checks were unchanged. Ruff and `git diff --check`
also pass.

Live PR #1169 was verified open and ready (`draft=false`). Its primary acceptance
list already checks four verified items, while its automated summary leaves the
same four unchecked. Updating that summary was attempted before further work,
but the connector returned: `MCP tool call requires approval, but approval policy
is never`. `PR_BODY.md` preserves the reconciled body; native Office acceptance
remains unchecked throughout. No live PR metadata was changed.

The workspace's `.git` is read-only. A focused commit is preserved in the local
clone `/tmp/counter-risk-1159-office-review`; the independently applicable patch
is `/tmp/counter-risk-1159-office.patch`. Applying that patch in a writable
checkout and publishing the reconciled PR body remain handoff actions.
