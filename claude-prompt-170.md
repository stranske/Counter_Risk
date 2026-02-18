# Autofix from CI failure

You are Codex running in autofix mode after a CI failure. Use the available logs and repository context to repair the failing checks.

Guidance:
- Inspect the latest CI output provided by the caller (logs or summaries) to pinpoint the root cause.
- Focus on minimal, targeted fixes that unblock the failing job.
- Leave diagnostic breadcrumbs when a failure cannot be reproduced or fully addressed.
- Re-run or suggest the smallest relevant checks to verify the fix.

## Run context
Gate run: https://github.com/stranske/Counter_Risk/actions/runs/22130163804
Conclusion: cancelled
PR: #170
Head SHA: c7b5ed1d8a4389d7ab2c0035cd4bb1e697c7cf97
Autofix attempts for this head: 1 / 2
Fix scope: src/, tests/, tools/, scripts/, agents/, templates/, .github/
Failing jobs: none reported.
