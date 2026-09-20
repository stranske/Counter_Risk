# Product contract — stranske/Counter_Risk
_First draft generated 2026-09-20 from the audit scorecard; the repo owns this file from now on. A PR that adds a user-facing route, command or page adds a line here. The audit's Phase 1.5 scores every line below and prints any surface not listed as UNSCORED._

## Purpose
Turn exposure workbooks into consolidated counterparty-risk outputs, alerts and monthly Excel/PowerPoint deliverables.

## Primary journey
Supply all workbook variants → run pipeline → review consolidated exposures, limits and concentration → receive reporting package.

## Core functions
| id | a <user> can … and sees … | entry point | probe (how to exercise it; vary these determinants) | status 2026-09-20 |
|---|---|---|---|---|
| C1 | an operator can load positions and sees coherent exposure by counterparty and variant | `counter-risk run --config <workflow.yml>` | run shipped three variants; vary synthetic position rows at concentration boundary | PARTIAL |
| C2 | an operator can apply identity and limits and sees aliases resolve with breached-cap warning | run; `limit_breaches.csv`, `DATA_QUALITY_SUMMARY.txt` | evaluate Citibank vs Citigroup under 40% cap; compare breach | WORKS |
| C3 | an operator can compute concentration and sees HHI, Top-5 and Top-10 reflecting consolidated gross exposure | run; `concentration_metrics.csv` and manifest | compare concentrated vs even portfolios and Citibank vs registered-alias split | BROKEN |
| C4 | an operator can produce monthly reporting and sees newly generated, consistent report artifacts and warnings | run; XLSX, PPTX/PDF, manifest/run folder | attempt full CLI run; compare fixture replay to live calculation | PARTIAL |

## Known gaps at draft time
- C1: full user-path run did not complete within the execution ceiling, and the CLI requires all three variants; output generation is unestablished.
- C3: a registered Citibank/Citigroup alias split changes HHI even though the limits evaluator resolves the same identity; risk concentration is wrong.
- C4: fixture replay copies existing artifacts rather than calculating, while live report/PDF generation was unestablished.
