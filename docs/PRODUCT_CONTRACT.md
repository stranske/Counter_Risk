# Product contract — stranske/Counter_Risk
_First draft generated 2026-09-20 from the audit scorecard; the repo owns this file from now on. A PR that adds a user-facing route, command or page adds a line here. The audit's Phase 1.5 scores every line below and prints any surface not listed as UNSCORED._

## Purpose
Turn exposure workbooks into consolidated counterparty-risk outputs, alerts and monthly Excel/PowerPoint deliverables.

## Primary journey
Supply all workbook variants → run pipeline → review consolidated exposures, limits and concentration → receive reporting package.

## Core functions
| id | a user can … and sees … | entry point | probe (how to exercise it; vary these determinants) | status 2026-09-27 |
|---|---|---|---|---|
| C1 | an operator can load positions and sees coherent exposure by counterparty and variant | `counter-risk run --config <workflow.yml>` | run shipped three variants; vary synthetic position rows at concentration boundary | WORKS (maintainer CLI) |
| C2 | an operator can apply identity and limits and sees aliases resolve with breached-cap warning | `counter-risk run --config <workflow.yml>` | use shipped absolute-notional Citibank cap; vary Citibank/Citigroup rows; inspect `limit_breaches.csv` and summary | WORKS |
| C3 | an operator can compute concentration and sees HHI, Top-5 and Top-10 reflecting consolidated gross exposure | `counter-risk run --config <workflow.yml>` | compare concentrated/even and registered-alias split portfolios; inspect metrics CSV and manifest | WORKS (maintainer CLI) |
| C4 | an operator can produce monthly reporting and sees newly generated, consistent report artifacts and warnings | `counter-risk run --config <workflow.yml>` | compare fixture replay to live calculation; inspect XLSX, PPTX/PDF and manifest/run folder | WORKS (maintainer CLI) |

## Current operator gaps and boundaries
- The Windows release bundle and final `Runner.xlsm` click behavior still require a Windows build plus the manual checks in `docs/RELEASE_CHECKLIST.md`; passing maintainer CLI coverage does not claim that operator release verification is complete.
- `Runner.xlsm` retains the `Ask about this run` label without a bound Form Control or VBA handler. Provider-backed chat also requires configured credentials.
- `counter-risk run --fixture-replay` is a packaging-validation path that copies checked-in fixtures by design. Monthly operators use workflow mode for current calculations.
