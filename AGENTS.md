# AGENTS.md

This file is the “mission briefing” for coding agents working in this repository. It is project-specific. For workflow/consumer-repo rules, also read **CLAUDE.md**.

## What this project is

Counter_Risk replaces a spreadsheet-based monthly counterparty risk process. The end state is:

- A maintainable program that ingests monthly inputs and produces the same outputs the spreadsheet produced (plus new output types later).
- A button-driven “Runner” so **non-technical operators** can run the process without a CLI and without repo access.
- A deterministic, testable pipeline with parity checks against “golden” reference artifacts.

## Non-technical operator workflow (no CLI)

Operators should be able to:

1. Pick an **as-of date** (and optionally a variant: All Programs / Ex Trend / Trend).
2. Click **Run**.
3. Receive an output folder containing:
   - Updated historical workbooks
   - Updated monthly PPT (and optionally a static distribution PPT/PDF)
   - A manifest and a short data quality summary

Operators never need to see GitHub, Python, or a terminal.

## Maintainer workflow (agent-driven)

Maintainers primarily work through issues and PRs:

- Issues should follow `docs/AGENT_ISSUE_FORMAT.md`
- Agent automation is driven by labels (see `WORKFLOW_USER_GUIDE.md`)
- Keepalive expects PR bodies to contain task checkboxes and acceptance criteria checkboxes

When writing issues, prefer:
- Small scope (one PR per issue)
- Objective acceptance criteria (range-level comparisons, file existence checks, deterministic metrics)
- Explicit file/module names when known

## Source artifacts and parity strategy

The pipeline must reproduce current outputs using the provided reference artifacts (fixtures). The project should maintain:

- A `tests/fixtures/` directory for **sanitized** reference files (Excel/PPT) used in regression tests.
- Range-level comparisons for key tables and time-series append logic.
- Structural checks for PPT (slide count, expected shapes present).
- A manifest file in each run output folder recording:
  - input hashes
  - output paths
  - warnings and reconciliation gaps
  - top exposures / top movers summaries

Never silently drop exposures. If a new counterparty appears and there is no matching historical series header, the run must warn or fail based on policy.

## Key technical constraints and “gotchas”

1. Date semantics must be explicit:
   - `as_of_date` is the effective reporting date used on historical workbook x-axes.
   - `run_date` is when the pipeline was executed.

2. Name normalization must be deterministic:
   - Trim/canonicalize whitespace.
   - Apply alias mapping registry first, then fallback mapping.
   - Treat Excel/PPT header series names as brittle (spaces and punctuation matter).

3. PowerPoint is hybrid:
   - Some slides are pasted screenshots (replace pictures).
   - Other slides are linked charts (OLE links) that may require refresh (COM automation preferred + fallback instruction file).

4. Workflows are synced from stranske/Workflows:
   - Do not edit `.github/workflows/**` unless explicitly operating under a high-privilege environment and the task requires it.
   - If workflow changes are needed, fix them in **stranske/Workflows** then sync.

## Agent guardrails (must follow)

- Also read: `.github/codex/AGENT_INSTRUCTIONS.md`
- Do not modify protected workflow/security files unless explicitly allowed.
- Do not introduce secrets into logs/files.
- Keep changes scoped to the PR’s tasks.

## Definition of done (per milestone)

Milestone 1 (Parity using MOSERS-formatted inputs):
- Parse MOSERS-format workbooks into canonical tables.
- Update historical workbooks by appending a new row.
- Update monthly PPT (screenshots replaced + links refreshed or static distribution output).
- Produce run manifest + data quality summary.

Milestone 2 (Remove VBA/manual prep):
- Ingest raw NISA monthly inputs and generate MOSERS-format structures without running macros.
- Automate cash ingestion (structured source preferred; PDF fallback + overrides).
- Add prior-month futures delta/sign-flip logic for Trend.

## Where to look for keepalive system docs

- `WORKFLOW_USER_GUIDE.md` (labels, triggers, operator usage)
- `docs/KEEPALIVE_TROUBLESHOOTING.md` (deep debugging and known failure modes)
- `CLAUDE.md` (consumer repo boundaries and “what not to edit”)
