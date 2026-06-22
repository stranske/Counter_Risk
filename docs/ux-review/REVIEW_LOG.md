# UX Review Log — Counter_Risk

Diff-anchored record of UX Review (`/ux-review`) passes. Each entry's commit SHA is the anchor the
next review diffs against to focus on new + likely-affected functionality. Detailed artifacts live in
`Orchestrator/ux_reviews/`.

## 2026-06-22 — GUI runner (`counter-risk gui`) — commit `1648d13` — overall 7.0/10 (gate PASS)

- **Coverage:** main window form rendered ✓; inline field help on Mode / Discovery Mode / Strict Policy / Formatting Profile ✓ (observed); first-launch clean state (no bare error) ✓. **NOT UI-driven** (Tk accessibility layer too sparse to click controls): Run → missing-root guidance (**function-verified**, not screencaptured); Browse… dialog; Dry-Run Discovery; post-run output display.
- **Scores:** wired 8.0 / usability 7.0 / help_clarity 6.0 / workflow 7.0.
- **Findings:** As-of Date / Input Root / Output Root lack inline help (usability+help, 4/4); missing-root guidance only surfaces on a Run attempt, not at launch (4/4); no persistent run-status indicator (3/4). → **filed #777**.
- **Prior:** 2.5/10 — no help mechanism at all + error-on-launch dead-end (#771 input-root guidance via PRs #773/#776, #772 field help via PR #775 — now fixed).
- **Next focus:** add a subprocess/AppleScript smoke harness that drives Run / Dry-Run / Browse and asserts the in-GUI guidance string (closes the Tk-automation coverage gap); re-check after #777.
