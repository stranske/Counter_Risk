# Autofix from CI failure

You are Codex running in autofix mode after a CI failure. Use the available logs and repository context to repair the failing checks.

Guidance:
- Inspect the latest CI output provided by the caller (logs or summaries) to pinpoint the root cause.
- Focus on minimal, targeted fixes that unblock the failing job.
- Leave diagnostic breadcrumbs when a failure cannot be reproduced or fully addressed.
- Re-run or suggest the smallest relevant checks to verify the fix.

## Run context
Gate run: https://github.com/stranske/Counter_Risk/actions/runs/22132488806
Conclusion: cancelled
PR: #164
Head SHA: 372d05af398d61c2d8ba544e47f8bbf267d717d9
Autofix attempts for this head: 1 / 2
Fix scope: src/, tests/, tools/, scripts/, agents/, templates/, .github/
Failing jobs: none reported.
