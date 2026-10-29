## Verified follow-up to issue #1219

PR #1221 was already merged before this keepalive run. Its unchecked nested
contract tasks are stale. This follow-up tests one remaining branch in the
issue's first-ranked target, `src/counter_risk/web_demo.py`.

A valid `input_discovery` mapping can omit `directory_roots`. Two new parameter
cases exercise relocation with an empty discovery mapping and with naming
patterns alone. Both verify the copied YAML, successful configuration loading,
default empty roots, preserved naming patterns, fixture source resolution, and
unchanged original YAML. No production change was necessary.

| Whole non-slow suite, targeted module measurement | Before | After |
| --- | ---: | ---: |
| Covered statements | 127/127 | 127/127 |
| Covered branches | 33/34 | 34/34 |
| Blended module coverage | 99.38% | 100% |
| Passing tests | 2,595 | 2,597 |
| Skipped tests | 1 | 1 |

Command: `pytest tests/ -n 4 -m 'not slow' -q -o addopts= --cov=counter_risk.web_demo --cov-branch --cov-report=term-missing`.
The final focused suite also passes: **53 passed, 1 deselected**, with the same
100% module coverage.

For each new parameter case, deliberately replacing the optional-roots type
guard with `if True` makes materialization attempt to iterate `None`. Each
individual mutated run fails with `TypeError` and exit 1. Restoring the source
byte-for-byte makes each selected case pass with exit 0. These experiments were
repeated after the Ruff setup adjustment. Actual commands and transcripts are in
[discovery-mutation-receipts.json](discovery-mutation-receipts.json).

Black formatted the changed Python file. The required repository-wide Black
check and CI variant both pass for 403 files, after warming a temporary cache
with the existing serial driver. Ruff passes with CI flags, and `git diff --check`
passes. Commands, full-suite output, and coverage summaries are in
[discovery-validation.json](discovery-validation.json).

- [x] Select the target by the issue's ranking and confirm its missing branch
  with a whole-suite baseline.
- [x] Verify both new cases with actual failing mutations and restored passing runs.
- [x] Verify the focused and whole non-slow suites and required formatting/lint checks.

This covers **one additional local branch**, with no reduction in missed lines.
The authoritative issue baseline remains **89.32% CI blended coverage**. CI now
configures line-only coverage; this explicitly enabled branch experiment does
not establish the requested approximately 180-unit CI reduction or completion
of the initiative. Earlier target accounting remains in the original PR's
evidence; no other module was remeasured in this follow-up.

The original checkout's `.git` directory is read-only. The tested files remain
in the workspace, and writable Git storage at `/tmp/issue-1219-discovery.git`
preserves the commit. Publication status is reported separately; local test
success is not evidence of hosted CI success.

Publication is blocked. Git push exits 128 because `github.com` cannot resolve.
The GitHub API upload, source-issue blocker comment, and `needs-human` label were
each rejected with `MCP tool call requires approval, but approval policy is never`.
No remote state changed, and no new PR was created. The portable commit bundle is
`/tmp/issue-1219-discovery.bundle`.

Refs #1219.
